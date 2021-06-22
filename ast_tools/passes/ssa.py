from collections import ChainMap, Counter
import builtins
import types
import functools as ft
import typing as tp

import libcst as cst
from libcst.metadata import ExpressionContext, ExpressionContextProvider, PositionProvider
from libcst import matchers as m

from ast_tools.common import gen_free_prefix
from ast_tools.cst_utils import DeepNode
from ast_tools.cst_utils import to_module, make_assign, to_stmt
from ast_tools.metadata import AlwaysReturnsProvider, IncrementalConditionProvider
from ast_tools.stack import SymbolTable
from ast_tools.transformers.node_tracker import NodeTrackingTransformer, with_tracking
from ast_tools.transformers.node_replacer import NodeReplacer
from ast_tools.transformers.normalizers import ElifToElse
from ast_tools.utils import BiMap
from . import Pass, PASS_ARGS_T

__ALL__ = ['ssa']

#([gaurds], expr])
_GAURDED_EXPR = tp.Tuple[tp.Sequence[cst.BaseExpression], cst.BaseExpression]

def _simplify_gaurds(
        gaurded_seq: tp.Sequence[_GAURDED_EXPR],
        ) -> tp.Sequence[_GAURDED_EXPR]:
    '''
    Pretty simplistic simplifyication
    which looks for:
        [
            ...,
            ([p, q], expri),
            ([p, not q], exprj),
            ...
        ]
    and simplifies it to:
        [
            ...,
            ([p, q], expri),
            ([p], exprj),
            ...
        ]
    also truncates the list after empty gaurds:
        [
            ...,
            ([], expr),
            ...
        ]
    becomes:
        [
            ...,
            ([], expr)
        ]
    '''
    # wrap the implementation so we can assert that
    # we reach a fixed point after a single invocation
    def impl(gaurded_seq):
        new_seq = [gaurded_seq[0]]
        for gaurd, expr in gaurded_seq[1:]:
            last_gaurd = new_seq[-1][0]
            # Truncate
            if not last_gaurd:
                break
            elif not gaurd:
                new_seq.append((gaurd, expr))
                break

            pred = gaurd[-1]
            if (isinstance(pred, cst.UnaryOperation)
                and isinstance(pred.operator, cst.Not)
                and pred.expression == last_gaurd[-1]
                and gaurd[:-1] == last_gaurd[:-1]):
                # simplify
                new_seq.append((gaurd[:-1], expr))
            else:
                new_seq.append((gaurd, expr))
        return new_seq

    new_seq = impl(gaurded_seq)
    assert new_seq == impl(new_seq)
    return new_seq


class IncompleteGaurdError(Exception): pass


def _fold_conditions(
        gaurded_seq: tp.Sequence[_GAURDED_EXPR],
        strict: bool,
        ) -> cst.BaseExpression:
    def and_builder(
            left: cst.BaseExpression,
            right: cst.BaseExpression
            ) -> cst.BooleanOperation:
        return cst.BooleanOperation(
                left=left,
                operator=cst.And(),
                right=right,
        )

    if not gaurded_seq and strict:
        raise IncompleteGaurdError()

    gaurd, expr = gaurded_seq[0]
    if not gaurd or (not strict and len(gaurded_seq) == 1):
        return expr
    else:
        if len(gaurd) == 1:
            test = gaurd[0]
        else:
            test = ft.reduce(and_builder, gaurd)

        conditional = cst.IfExp(
                test=test,
                body=expr,
                orelse=_fold_conditions(gaurded_seq[1:], strict)
            )
        return conditional


class NameTests(NodeTrackingTransformer):
    '''
    Rewrites if statements so that their tests are a single name
    This gaurentees that the conditions are ssa
    e.g:
        if x == 0:
            ...
        else:
            ...
    becomes:
        cond = x == 0
        if cond:
            ...
        else:
            ...
    '''
    format: str
    added_names: tp.MutableSet[str]

    def __init__(self, prefix):
        super().__init__()
        self.format = prefix+'_{}'
        self.added_names = set()

    def leave_If(self,
            original_node: cst.If,
            updated_node: cst.If,
            ) -> cst.If:
        c_name = cst.Name(value=self.format.format(len(self.added_names)))
        self.added_names.add(c_name.value)
        assign = to_stmt(make_assign(c_name, updated_node.test))
        final_node = updated_node.with_changes(test=c_name)
        return cst.FlattenSentinel([assign, final_node])


class SingleReturn(NodeTrackingTransformer):
    METADATA_DEPENDENCIES = (IncrementalConditionProvider, AlwaysReturnsProvider)

    attr_format: tp.Optional[str]
    attr_states: tp.MutableMapping[str, tp.MutableSequence[_GAURDED_EXPR]]
    strict: bool
    debug: bool
    env: tp.Mapping[str, tp.Any]
    names_to_attr: tp.Mapping[str, cst.Attribute]
    return_format: tp.Optional[str]
    returns: tp.MutableSequence[_GAURDED_EXPR]
    scope: tp.Optional[cst.FunctionDef]
    tail: tp.MutableSequence[cst.BaseStatement]
    added_names: tp.MutableSet[str]
    returning_blocks: tp.MutableSet[cst.BaseSuite]

    def __init__(self,
            env: tp.Mapping[str, tp.Any],
            names_to_attr: tp.Mapping[str, cst.Attribute],
            strict: bool = True,
            ):

        super().__init__()
        self.attr_format = None
        self.attr_states = {}
        self.strict = strict
        self.env = env
        self.names_to_attr = names_to_attr
        self.returns = []
        self.return_format = None
        self.scope = None
        self.tail = []
        self.added_names = set()
        self.returning_blocks = set()

    def visit_FunctionDef(self,
            node: cst.FunctionDef) -> tp.Optional[bool]:
        # prevent recursion into inner functions
        super().visit_FunctionDef(node)
        if self.scope is None:
            self.scope = node
            prefix = gen_free_prefix(node, self.env, '__')
            self.attr_format = prefix + '_final_{}_{}_{}'
            self.return_format = prefix + '_return_{}'

            return True
        return False

    def leave_FunctionDef(self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef
            ) -> cst.FunctionDef:
        final_node = updated_node
        if original_node is self.scope:
            suite = updated_node.body
            tail = self.tail
            for name, attr in self.names_to_attr.items():
                state = self.attr_states.get(name, [])
                # default writeback initial value
                state.append(([], cst.Name(name)))
                attr_val = _fold_conditions(_simplify_gaurds(state), self.strict)
                write = to_stmt(make_assign(attr, attr_val))
                tail.append(write)

            if self.returns:
                strict = self.strict

                try:
                    return_val = _fold_conditions(_simplify_gaurds(self.returns), strict)
                except IncompleteGaurdError:
                    raise SyntaxError('Cannot prove function always returns') from None
                return_stmt = cst.SimpleStatementLine([cst.Return(value=return_val)])
                tail.append(return_stmt)

        return final_node

    def visit_ClassDef(self,
            node: cst.ClassDef) -> tp.Optional[bool]:
        return False

    def leave_Return(self,
            original_node: cst.Return,
            updated_node: cst.Return
            ) -> cst.RemovalSentinel:
        assert self.return_format is not None
        assert self.attr_format is not None

        assignments = []
        cond = self.get_metadata(IncrementalConditionProvider, original_node)

        for name, attr in self.names_to_attr.items():
            assert isinstance(attr.value, cst.Name)
            state = self.attr_states.setdefault(name, [])
            attr_name = cst.Name(
                    value=self.attr_format.format(
                        attr.value.value,
                        attr.attr.value,
                        len(state)
                    )
                )
            self.added_names.add(attr_name.value)
            state.append((cond, attr_name))
            assignments.append(make_assign(attr_name, cst.Name(name)))

        r_name = cst.Name(value=self.return_format.format(len(self.returns)))
        self.added_names.add(r_name.value)
        self.returns.append((cond, r_name))

        if updated_node.value is None:
            r_val = cst.Name(value='None')
        else:
            r_val = updated_node.value

        assignments.append(make_assign(r_name, r_val))

        return cst.FlattenSentinel(assignments)

    def leave_SimpleStatementSuite(self,
            original_node: cst.SimpleStatementSuite,
            updated_node: cst.SimpleStatementSuite,
            ) -> cst.SimpleStatementSuite:
        final_node = super().leave_SimpleStatementSuite(original_node, updated_node)
        if self.get_metadata(AlwaysReturnsProvider, original_node):
            self.returning_blocks.add(final_node)
        return final_node

    def leave_IndentedBlock(self,
            original_node: cst.IndentedBlock,
            updated_node: cst.IndentedBlock,
            ) -> cst.IndentedBlock:
        final_node = super().leave_IndentedBlock(original_node, updated_node)
        if self.get_metadata(AlwaysReturnsProvider, original_node):
            self.returning_blocks.add(final_node)
        return final_node


class WrittenAttrs(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (ExpressionContextProvider,)

    written_attrs: tp.MutableSet[cst.Attribute]

    def __init__(self):
        super().__init__()
        self.written_attrs = set()


    def visit_Attribute(self,
            node: cst.Attribute) -> tp.Optional[bool]:
        ctx = self.get_metadata(ExpressionContextProvider, node)
        if ctx is ExpressionContext.STORE:
            self.written_attrs.add(node)


class AttrReplacer(NodeReplacer):
    def _get_key(self, node):
        if isinstance(node, cst.Attribute):
            return DeepNode(node)
        else:
            return None


def _wrap(tree: cst.CSTNode) -> cst.MetadataWrapper:
    return cst.MetadataWrapper(tree, unsafe_skip_copy=True)


class SSATransformer(NodeTrackingTransformer):
    env: tp.Mapping[str, tp.Any]
    ctxs: tp.Mapping[cst.Name, ExpressionContext]
    scope: tp.Optional[cst.FunctionDef]
    name_table: tp.ChainMap[str, str]
    name_idx: Counter
    name_formats: tp.MutableMapping[str, str]
    name_assignments: tp.MutableMapping[str, tp.Union[cst.Assign, cst.Param]]
    original_names: tp.MutableMapping[str, str]
    final_names: tp.AbstractSet[str]
    returning_blocks: tp.AbstractSet[cst.BaseSuite]
    _skip: bool
    _assigned_names: tp.MutableSequence[str]


    def __init__(self,
            env: tp.Mapping[str, tp.Any],
            ctxs: tp.Mapping[cst.Name, ExpressionContext],
            final_names: tp.AbstractSet[str],
            returning_blocks: tp.AbstractSet[cst.BaseSuite],
            strict: bool = True,
            ):
        super().__init__()
        _builtins = env.get('__builtins__', builtins)
        if isinstance(_builtins, types.ModuleType):
            _builtins = builtins.__dict__
        self.env = ChainMap(env, _builtins)
        self.ctxs = ctxs
        self.scope = None
        self.name_assignments = ChainMap()
        self.name_idx = Counter()
        self.name_table = ChainMap({k: k for k in self.env})
        self.name_formats = {}
        self.original_names = {}
        self.final_names = final_names
        self.strict = strict
        self.returning_blocks = returning_blocks
        self._skip = 0
        self._assigned_names = []


    def _make_name(self, name):
        if name not in self.name_formats:
            prefix = gen_free_prefix(self.scope, self.env, f'{name}_')
            self.name_formats[name] = prefix + '{}'

        ssa_name = self.name_formats[name].format(self.name_idx[name])
        self.name_idx[name] += 1
        self.name_table[name] = ssa_name
        self.original_names[ssa_name] = name
        return ssa_name

    def visit_FunctionDef(self,
            node: cst.FunctionDef) -> tp.Optional[bool]:
        # prevent recursion into inner functions
        # and control recursion
        if self.scope is None:
            self.scope = node
        return False

    def leave_FunctionDef(self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef) -> cst.FunctionDef:
        final_node = updated_node
        if original_node is self.scope:
            # Don't want to ssa params but do want them in the name table
            for param in updated_node.params.params:
                name = param.name.value
                self.name_table[name] = name
                self.name_assignments[name] = param

            # Need to visit params to get them to be rebuilt and therfore
            # tracked to build the symbol table
            update_params = updated_node.params.visit(self)
            assert not self._skip
            assert not self._assigned_names, self._assigned_names
            new_body = updated_node.body.visit(self)
            final_node = updated_node.with_changes(body=new_body, params=update_params)
            assert not self._skip
            assert not self._assigned_names, self._assigned_names
        return final_node

    def visit_If(self, node: cst.If) -> tp.Optional[bool]:
        super().visit_If(node)
        # Control recursion order
        return False

    def leave_If(self,
            original_node: cst.If,
            updated_node: cst.If,
            ) -> tp.Union[cst.If, cst.RemovalSentinel]:
        t_returns = original_node.body in self.returning_blocks
        if original_node.orelse is not None:
            f_returns = original_node.orelse.body in self.returning_blocks
        else:
            f_returns = False

        new_test = updated_node.test.visit(self)
        nt = self.name_table
        suite = []
        self.name_table = t_nt = nt.new_child()
        new_body = updated_node.body.visit(self)

        suite.extend(new_body.body)

        self.name_table = f_nt = nt.new_child()
        orelse = updated_node.orelse
        if orelse is not None:
            assert isinstance(orelse, cst.Else)
            new_orelse = orelse.visit(self)
            suite.extend(new_orelse.body.body)
        else:
            assert not f_returns

        self.name_table = nt

        t_nt = t_nt.maps[0]
        f_nt = f_nt.maps[0]


        def _mux_name(name, t_name, f_name):
            new_name = self._make_name(name)
            assign = make_assign(
                cst.Name(new_name),
                cst.IfExp(
                    test=new_test,
                    body=cst.Name(t_name),
                    orelse=cst.Name(f_name),
                ),
            )
            self.name_assignments[new_name] = assign

            stmt = to_stmt(assign)

            assert isinstance(original_node, cst.If)
            assert isinstance(self.name_assignments[t_name], (cst.Assign, cst.Param))
            assert isinstance(self.name_assignments[f_name], (cst.Assign, cst.Param))
            self.track_with_children((
                self.name_assignments[t_name],
                self.name_assignments[f_name],
                original_node,
                ),  stmt)
            assert assign in self.node_tracking_table.i
            return stmt

        if t_returns and f_returns:
            # No need to mux any names they can't fall through anyway
            pass
        elif t_returns and not f_returns:
            # fall through from orelse
            nt.update(f_nt)
        elif f_returns and not t_returns:
            # fall through from body
            nt.update(t_nt)
        else:
            # Mux names
            for name in sorted(t_nt.keys() | f_nt.keys()):
                if name in t_nt and name in f_nt:
                    # mux between true and false
                    suite.append(_mux_name(name, t_nt[name], f_nt[name]))
                elif name in t_nt and name in nt:
                    # mux between true and old value
                       suite.append(_mux_name(name, t_nt[name], nt[name]))
                elif name in f_nt and name in nt:
                    # mux between false and old value
                    suite.append(_mux_name(name, nt[name], f_nt[name]))
                elif name in t_nt and not self.strict:
                    # Assume name will fall through
                    nt[name] = t_nt[name]
                elif name in f_nt and not self.strict:
                    # Assume name will fall through
                    nt[name] = f_nt[name]


        return cst.FlattenSentinel(suite)

    def visit_Assign(self, node: cst.Assign) -> tp.Optional[bool]:
        # Control recursion order
        return False

    def leave_Assign(self,
            original_node: cst.Assign,
            updated_node: cst.Assign) -> cst.Assign:
        new_value = updated_node.value.visit(self)
        assert not self._assigned_names, (to_module(original_node).code, self._assigned_names)
        new_targets =  [t.visit(self) for t in updated_node.targets]
        final_node = updated_node.with_changes(value=new_value, targets=new_targets)
        for name in self._assigned_names:
            self.name_assignments[name] = original_node
        self._assigned_names = []
        return final_node

    def visit_Attribute(self, node: cst.Attribute) -> tp.Optional[bool]:
        return False

    def leave_Attribute(self,
            original_node:  cst.Attribute,
            updated_node: cst.Attribute) -> cst.Attribute:
        new_value = updated_node.value.visit(self)
        final_node = updated_node.with_changes(value=new_value)
        return final_node

    def visit_Arg_keyword(self, node: cst.Arg):
        self._skip += 1

    def leave_Arg_keyword(self, node: cst.Arg):
        self._skip -= 1

    def visit_Parameters(self, node: cst.Parameters) -> tp.Optional[bool]:
        self._skip += 1
        return True

    def leave_Parameters(self,
            original_node: cst.Parameters,
            updated_node: cst.Parameters) -> cst.Parameters:
        self._skip -= 1
        return updated_node

    def leave_Name(self,
            original_node: cst.Name,
            updated_node: cst.Name) -> cst.Name:
        if self._skip:
            return updated_node

        name = updated_node.value
        # name is already ssa
        if name in self.final_names:
            return updated_node

        ctx = self.ctxs[original_node]
        if ctx is ExpressionContext.LOAD:
            # Names in Load context should not be added to the name table
            # as it makes them seem like they have been modified.
            try:
                return cst.Name(self.name_table[name])
            except KeyError:
                if self.strict:
                    raise SyntaxError(f'Cannot prove name `{name}` is defined')
                else:
                    return cst.Name(name)
        elif ctx is ExpressionContext.STORE:
            new_name = self._make_name(name)
            self._assigned_names.append(new_name)
            return cst.Name(new_name)
        else:
            return updated_node

class GenerateSymbolTable(cst.CSTVisitor):
    node_tracking_table: BiMap[cst.CSTNode, cst.CSTNode]

    def __init__(self, node_tracking_table, original_names, pos_info, start_ln, end_ln):
        self.node_tracking_table = node_tracking_table
        self.original_names = original_names
        self.pos_info = pos_info
        self.start_ln = start_ln
        self.end_ln = end_ln
        self.symbol_table = {
            i: {} for i in range(start_ln, end_ln+1)
        }
        self.scope = None


    def _set_name(self, name, new_name, origins):
        ln = self.start_ln
        for origin in origins:
            pos = self.pos_info[origin]

            if isinstance(origin, (cst.BaseExpression, cst.BaseSmallStatement, cst.Param)):
                ln = max(ln, pos.end.line)
            else:
                assert isinstance(origin, cst.BaseCompoundStatement)
                ln = max(ln, pos.end.line + 1)

        for i in range(ln, self.end_ln+1):
            self.symbol_table[i][name] = new_name


    def visit_FunctionDef(self,
            node: cst.FunctionDef) -> tp.Optional[bool]:
        if self.scope is None:
            self.scope = node
            return True
        return False

    def visit_Param(self, node: cst.Param) -> tp.Optional[bool]:
        name = node.name.value
        origins = self.node_tracking_table.i[node]
        self._set_name(name, name, origins)

    def visit_Assign(self, node: cst.Assign) -> tp.Optional[bool]:
        for t in node.targets:
            t = t.target
            if m.matches(t, m.Name()):
                ssa_name = t.value
                if ssa_name in self.original_names:
                    ln = self.start_ln
                    name = self.original_names[ssa_name]
                    # HACK attrs not currently tracked properly
                    try:
                        origins = self.node_tracking_table.i[t]
                    except KeyError:
                        continue
                    self._set_name(name, ssa_name, origins)

class ssa(Pass):
    def __init__(self, strict: bool = True):
        self.strict = strict

    def rewrite(self,
            original_tree: cst.FunctionDef,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:
        if not isinstance(original_tree, cst.FunctionDef):
            raise TypeError('ssa must be run on a FunctionDef')


        # resolve position information necessary for generating symbol table
        wrapper = _wrap(to_module(original_tree))
        pos_info = wrapper.resolve(PositionProvider)

        # convert `elif cond:` to `else: if cond:`
        # (simplifies ssa logic)
        transformer = with_tracking(ElifToElse)()
        tree = original_tree.visit(transformer)

        # original node -> generated nodes
        node_tracking_table = transformer.node_tracking_table
        # node_tracking_table.i
        # generated node -> original nodes

        wrapper = _wrap(to_module(tree))
        writter_attr_visitor = WrittenAttrs()
        wrapper.visit(writter_attr_visitor)

        replacer = with_tracking(AttrReplacer)()
        attr_format = gen_free_prefix(tree, env, '_attr') + '_{}_{}'
        init_reads = []
        names_to_attr = {}
        seen = set()

        for written_attr in writter_attr_visitor.written_attrs:
            d_attr = DeepNode(written_attr)
            if d_attr in seen:
                continue
            if not isinstance(written_attr.value, cst.Name):
                raise NotImplementedError('writing non name nodes is not supported')

            seen.add(d_attr)

            attr_name = attr_format.format(
                    written_attr.value.value,
                    written_attr.attr.value,
                )

            # using normal node instead of original node
            # is safe as parenthesis don't matter:
            #  (name).attr == (name.attr) == name.attr
            norm = d_attr.normal_node
            names_to_attr[attr_name] = norm
            name = cst.Name(attr_name)
            replacer.add_replacement(written_attr, name)
            read = to_stmt(make_assign(name, norm))
            init_reads.append(read)

        # Replace references to attr with the name generated above
        tree = tree.visit(replacer)


        node_tracking_table = replacer.trace_origins(node_tracking_table)

        # Rewrite conditions to be ssa
        cond_prefix = gen_free_prefix(tree, env, '_cond')
        wrapper = _wrap(tree)
        name_tests = NameTests(cond_prefix)
        tree = wrapper.visit(name_tests)

        node_tracking_table = name_tests.trace_origins(node_tracking_table)


        # Transform to single return format
        wrapper = _wrap(tree)
        single_return = SingleReturn(env, names_to_attr, self.strict)
        tree = wrapper.visit(single_return)

        node_tracking_table = single_return.trace_origins(node_tracking_table)

        # insert the initial reads / final writes / return
        body = tree.body
        body = body.with_changes(body=(*init_reads, *body.body, *single_return.tail))
        tree = tree.with_changes(body=body)

        # perform ssa
        wrapper = _wrap(to_module(tree))
        ctxs = wrapper.resolve(ExpressionContextProvider)
        # These names were constructed in such a way that they are
        # guaranteed to be ssa and shouldn't be touched by the
        # transformer
        final_names = single_return.added_names | name_tests.added_names
        ssa_transformer = SSATransformer(
                env,
                ctxs,
                final_names,
                single_return.returning_blocks,
                strict=self.strict)
        tree = tree.visit(ssa_transformer)

        node_tracking_table = ssa_transformer.trace_origins(node_tracking_table)

        tree.validate_types_deep()
        # generate symbol table
        start_ln = pos_info[original_tree].start.line
        end_ln = pos_info[original_tree].end.line
        visitor = GenerateSymbolTable(
                node_tracking_table,
                ssa_transformer.original_names,
                pos_info,
                start_ln,
                end_ln,
        )

        tree.visit(visitor)
        metadata.setdefault('SYMBOL-TABLE', list()).append((type(self), visitor.symbol_table))
        return tree, env, metadata

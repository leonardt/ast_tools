from collections import ChainMap, Counter
import builtins
import types
import functools as ft
import typing as tp

import libcst as cst
from libcst.metadata import ExpressionContext, ExpressionContextProvider

from ast_tools.common import gen_free_prefix
from ast_tools.cst_utils import InsertStatementsVisitor, DeepNode
from ast_tools.cst_utils import to_module, make_assign
from ast_tools.metadata import AlwaysReturnsProvider, IncrementalConditionProvider
from ast_tools.transformers.node_replacer import NodeReplacer
from ast_tools.transformers.normalizers import ElifToElse
from ast_tools.stack import SymbolTable
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


class NameTests(InsertStatementsVisitor):
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
        super().__init__(cst.codemod.CodemodContext())
        self.format = prefix+'_{}'
        self.added_names = set()

    def leave_If(self,
            original_node: cst.If,
            updated_node: cst.If,
            ) -> cst.If:
        c_name = cst.Name(value=self.format.format(len(self.added_names)))
        self.added_names.add(c_name.value)
        assign = make_assign(c_name, updated_node.test)
        self.insert_statements_before_current([assign])
        final_node = updated_node.with_changes(test=c_name)
        return super().leave_If(original_node, final_node)


class SingleReturn(InsertStatementsVisitor):
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
    tail: tp.MutableSequence[tp.Union[cst.BaseStatement, cst.BaseSmallStatement]]
    added_names: tp.MutableSet[str]
    returning_blocks: tp.MutableSet[cst.BaseSuite]


    def __init__(self,
            env: tp.Mapping[str, tp.Any],
            names_to_attr: tp.Mapping[str, cst.Attribute],
            strict: bool = True,
            ):

        super().__init__(cst.codemod.CodemodContext())
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
                tail.append(make_assign(attr, attr_val))

            if self.returns:
                strict = self.strict

                try:
                    return_val = _fold_conditions(_simplify_gaurds(self.returns), strict)
                except IncompleteGaurdError:
                    raise SyntaxError('Cannot prove function always returns') from None
                return_stmt = cst.SimpleStatementLine([cst.Return(value=return_val)])
                tail.append(return_stmt)

        return super().leave_FunctionDef(original_node, final_node)

    def visit_ClassDef(self,
            node: cst.ClassDef) -> tp.Optional[bool]:
        super().visit_ClassDef(node)
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

        self.insert_statements_before_current(assignments)
        return super().leave_Return(original_node, cst.RemoveFromParent())

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


class SSATransformer(InsertStatementsVisitor):
    env: tp.Mapping[str, tp.Any]
    ctxs: tp.Mapping[cst.Name, ExpressionContext]
    scope: tp.Optional[cst.FunctionDef]
    name_table: ChainMap
    name_idx: Counter
    name_formats: tp.MutableMapping[str, str]
    final_names: tp.AbstractSet[str]
    returning_blocks: tp.AbstractSet[cst.BaseSuite]
    _in_keyword: bool

    def __init__(self,
            env: tp.Mapping[str, tp.Any],
            ctxs: tp.Mapping[cst.Name, ExpressionContext],
            final_names: tp.AbstractSet[str],
            returning_blocks: tp.AbstractSet[cst.BaseSuite],
            strict: bool = True,
            ):
        super().__init__(cst.codemod.CodemodContext())
        _builtins = env.get('__builtins__', builtins)
        if isinstance(_builtins, types.ModuleType):
            _builtins = builtins.__dict__
        self.env = ChainMap(env, _builtins)
        self.ctxs = ctxs
        self.scope = None
        self.name_idx = Counter()
        self.name_table = ChainMap({k: k for k in self.env})
        self.name_formats = {}
        self.final_names = final_names
        self.strict = strict
        self.returning_blocks = returning_blocks
        self._in_keyword = False


    def _make_name(self, name):
        if name not in self.name_formats:
            prefix = gen_free_prefix(self.scope, self.env, f'{name}_')
            self.name_formats[name] = prefix + '{}'

        ssa_name = self.name_formats[name].format(self.name_idx[name])
        self.name_idx[name] += 1
        self.name_table[name] = ssa_name
        return ssa_name

    def visit_FunctionDef(self,
            node: cst.FunctionDef) -> tp.Optional[bool]:
        # prevent recursion into inner functions
        # and control recursion
        super().visit_FunctionDef(node)
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

            new_body = updated_node.body.visit(self)
            final_node = updated_node.with_changes(body=new_body)

        return super().leave_FunctionDef(original_node, final_node)

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
            return make_assign(
                    cst.Name(self._make_name(name)),
                    cst.IfExp(
                        test=new_test,
                        body=cst.Name(t_name),
                        orelse=cst.Name(f_name),
                    ),
                )

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


        self.insert_statements_after_current(suite)
        return super().leave_If(original_node, cst.RemoveFromParent())

    def visit_Assign(self, node: cst.Assign) -> tp.Optional[bool]:
        # Control recursion order
        super().visit_Assign(node)
        return False

    def leave_Assign(self,
            original_node: cst.Assign,
            updated_node: cst.Assign) -> cst.Assign:
        new_value = updated_node.value.visit(self)
        new_targets =  [t.visit(self) for t in updated_node.targets]
        final_node = updated_node.with_changes(value=new_value, targets=new_targets)
        return super().leave_Assign(original_node, final_node)

    def visit_Attribute(self, node: cst.Attribute) -> tp.Optional[bool]:
        return False

    def leave_Attribute(self,
            original_node:  cst.Attribute,
            updated_node: cst.Attribute) -> cst.Attribute:
        new_value = updated_node.value.visit(self)
        final_node = updated_node.with_changes(value=new_value)
        return super().leave_Attribute(original_node, final_node)

    def visit_Arg_keyword(self, node: cst.Arg):
        self._in_keyword = True

    def leave_Arg_keyword(self, node: cst.Arg):
        self._in_keyword = False

    def leave_Name(self,
            original_node: cst.Name,
            updated_node: cst.Name) -> cst.Name:
        if self._in_keyword:
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
        else:
            return cst.Name(self._make_name(name))


class ssa(Pass):
    def __init__(self, strict: bool = True):
        self.strict = strict

    def rewrite(self,
            tree: cst.FunctionDef,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:
        if not isinstance(tree, cst.FunctionDef):
            raise TypeError('ssa must be run on a FunctionDef')

        wrapper = _wrap(to_module(tree))
        writter_attr_visitor = WrittenAttrs()
        wrapper.visit(writter_attr_visitor)

        replacer = AttrReplacer()
        attr_format = gen_free_prefix(tree, env, '_attr') + '_{}_{}'
        init_reads = []
        names_to_attr = {}
        seen = set()

        for written_attr in writter_attr_visitor.written_attrs:
            d_attr = DeepNode(written_attr)
            if d_attr in seen:
                continue
            elif not isinstance(written_attr.value, cst.Name):
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
            init_reads.append(make_assign(name, norm))

        # Replace references to attr with the name generated above
        tree = tree.visit(replacer)

        # Rewrite conditions to be ssa
        cond_prefix = gen_free_prefix(tree, env, '_cond')
        wrapper = _wrap(tree)
        name_tests = NameTests(cond_prefix)
        tree = wrapper.visit(name_tests)

        # convert `elif cond:` to `else: if cond:`
        # (simplifies ssa logic)
        tree = tree.visit(ElifToElse())

        # Transform to single return format
        wrapper = _wrap(tree)
        single_return = SingleReturn(env, names_to_attr, self.strict)
        tree = wrapper.visit(single_return)

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

        tree.validate_types_deep()
        return tree, env, metadata

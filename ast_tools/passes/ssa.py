import ast
from collections import ChainMap, Counter
from copy import deepcopy
import typing as tp

from . import Pass
from . import PASS_ARGS_T
from ast_tools.common import gen_free_prefix, gen_free_name, is_free_name
from ast_tools.immutable_ast import immutable, mutable
from ast_tools.stack import SymbolTable
from ast_tools.transformers import Renamer
from ast_tools.transformers.node_replacer import NodeReplacer
from ast_tools.visitors import collect_targets

__ALL__ = ['ssa']

class AttrReplacer(NodeReplacer):
    def _get_key(self, node):
        if isinstance(node, ast.Attribute):
            # Need the immutable value so its comparable
            return immutable(node)
        else:
            return None

def _flip_ctx(node):
    node = deepcopy(node)
    if isinstance(node.ctx, ast.Store):
        node.ctx = ast.Load()
    else:
        assert isinstance(node.ctx, ast.Load)
        node.ctx = ast.Store()
    return node

class SSATransformer(ast.NodeTransformer):
    def __init__(self,
            env: SymbolTable,
            return_value_prefix: str,
            attr_names: tp.Sequence[str],
            strict: bool):
        self.attr_names = attr_names
        self.attr_states = {name: [] for name in attr_names}
        self.env = env
        self.name_idx = Counter()
        self.name_table = ChainMap()
        self.root = None
        self.cond_stack = []
        self.return_value_prefix = return_value_prefix
        self.returns = []
        self.strict = strict


    def _make_name(self, name):
        new_name = name + str(self.name_idx[name])
        self.name_idx[name] += 1
        while not is_free_name(self.root, self.env, new_name):
            new_name = name + str(self.name_idx[name])
            self.name_idx[name] += 1

        self.name_table[name] = new_name
        return new_name


    def _make_return(self):
        p = self.return_value_prefix
        name = p + str(self.name_idx[p])
        self.name_idx[p] += 1
        return ast.Name(name, ast.Load())


    def visit(self, node: ast.AST) -> ast.AST:
        # basically want to able to visit a top level function
        # but don't want to generally recurse into them
        if self.root is None:
            self.root = node
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    arg_name = arg.arg
                    self.name_table[arg_name] = arg_name
            else:
                raise TypeError('SSATransformer must be rooted at a function')

            if self.strict:
                _prove_names_defined(self.env, self.name_table.keys(), node.body)
                if not _always_returns(node.body) and not _never_returns(node.body):
                    raise SyntaxError(f'Cannot prove {node.name} returns')
            return super().generic_visit(node)
        else:
            return super().visit(node)


    def visit_Assign(self, node):
        # visit RHS first
        node.value = self.visit(node.value)
        node.targets = [self.visit(t) for t in node.targets]
        return node


    def visit_If(self, node: ast.If) -> tp.List[ast.stmt]:
        test = self.visit(node.test)
        nt = self.name_table
        suite = []

        # determine if either branch always returns
        t_returns = _always_returns(node.body)
        f_returns = _always_returns(node.orelse)

        self.name_table = t_nt = nt.new_child()
        self.cond_stack.append(test)

        # gather nodes from the body
        for child in node.body:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, tp.Sequence):
                suite.extend(child)
            else:
                suite.append(child)

        self.cond_stack.pop()

        # Add not condition to the stack if the true branch
        # does not always return
        # the idea being that:
        #   if x:
        #       return 0
        #   else:
        #       return 1
        #   return 2
        #
        # should become:
        #    return 0 if x else 1
        #
        # where:
        #   if x:
        #       if y:
        #           return 0
        #   else:
        #       return 1
        #   return 2
        #
        # should become:
        #   return 0 if x and y else 1 if not x else 2
        if not t_returns:
            self.cond_stack.append(ast.UnaryOp(ast.Not(), test))

        self.name_table = f_nt = nt.new_child()

        # gather nodes from the orelse
        for child in node.orelse:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, tp.Sequence):
                suite.extend(child)
            else:
                suite.append(child)

        if not t_returns:
            self.cond_stack.pop()
        self.name_table = nt

        # Note by first checking for fall through conditions
        # then muxing construction of unnecessary muxes is avoided.
        # However it does obscure program logic somewhat as it will
        # appear as if old values of names are used.
        # e.g.:
        #   if cond:
        #       var = 1
        #   else:
        #       var = 2
        #       return 0
        #   return var
        #
        # becomes:
        #   var0 = 1
        #   var1 = 2
        #   __return_value0 = 0
        #   __return_value1 = var0
        #   return __return_value0 if not cond else __return_value1
        #
        # instead of:
        #   var0 = 1
        #   var1 = 2
        #   __return_value0 = 0
        #   var2 = var0 if cond else var1
        #   __return_value1 = var2
        #   return __return_value0 if not cond else __return_value1

        # only care about new / modified names
        t_nt = t_nt.maps[0]
        f_nt = f_nt.maps[0]

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
            # mux names
            def _build_name(name):
                return ast.Name(
                        id=name,
                        ctx=ast.Load(),
                    )

            def _mux_name(name, t_name, f_name):
                return ast.Assign(
                        targets=[
                            ast.Name(
                                id=self._make_name(name),
                                ctx=ast.Store(),
                            ),
                        ],
                        value=ast.IfExp(
                            test=test,
                            body=_build_name(t_name),
                            orelse=_build_name(f_name),
                        ),
                    )

            # names in body, names in orelse
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

        return suite


    def visit_Name(self, node: ast.Name) -> ast.Name:
        name = node.id
        ctx = node.ctx
        if isinstance(ctx, ast.Load):
            # Names in Load context should not be added to the name table
            # as it makes them seem like they have been modified.
            try:
                return ast.Name(
                        id=self.name_table[name],
                        ctx=ctx)
            except KeyError:
                pass
            return ast.Name(
                    id=name,
                    ctx=ctx)
        else:
            return ast.Name(
                    id=self._make_name(name),
                    ctx=ctx)


    def visit_Return(self, node: ast.Return) -> ast.Assign:
        # Record the state of each attr_name
        stack = list(self.cond_stack)
        for name in self.attr_names:
            self.attr_states[name].append((
                stack,
                ast.Name(self.name_table[name], ast.Load())))

        # Record the return value
        r_val = self.visit(node.value)
        r_name = self._make_return()
        self.returns.append((stack, r_name))
        return ast.Assign(
            targets=[ast.Name(r_name, ast.Store())],
            value=r_val,
        )


    # don't support control flow other than if
    def visit_For(self, node: ast.For):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_AsyncFor(self, node: ast.AsyncFor):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_While(self, node: ast.While):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_With(self, node: ast.With):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_AsyncWith(self, node: ast.AsyncWith):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_Try(self, node: ast.Try):
        raise SyntaxError(f"Cannot handle node {node}")

    # don't recurs into defs, but do rename them
    def visit_ClassDef(self, node: ast.ClassDef):
        renamer = Renamer(self.name_table.new_child())
        return renamer.visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        renamer = Renamer(self.name_table.new_child())
        return renamer.visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        renamer = Renamer(self.name_table.new_child())
        return renamer.visit(node)


def _prove_names_defined(
        env: SymbolTable,
        names: tp.AbstractSet[str],
        node: tp.Union[ast.AST, tp.Sequence[ast.AST]]) -> tp.AbstractSet[str]:
    '''
    Prove that all names are defined.
    i.e. if a name is used at some point then all paths leading to that point
    must either return or define the name.
    '''
    names = set(names)
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif node.id not in names and node.id not in env and \
                node.id not in env["__builtins__"].__dict__:
            if hasattr(node, 'lineno'):
                raise SyntaxError(f'Cannot prove name, {node.id}, is defined at line {node.lineno}')
            else:
                raise SyntaxError(f'Cannot prove name, {node.id}, is defined')

    elif isinstance(node, ast.If):
        t_returns = _always_returns(node.body)
        f_returns = _always_returns(node.orelse)
        t_names = _prove_names_defined(env, names, node.body)
        f_names = _prove_names_defined(env, names, node.orelse)
        if not (t_returns or f_returns):
            names |= t_names & f_names
        elif t_returns:
            names |= f_names
        elif f_returns:
            names |= t_names
    elif isinstance(node, ast.AST):
        for child in ast.iter_child_nodes(node):
            names |= _prove_names_defined(env, names, child)
    else:
        assert isinstance(node, tp.Sequence)
        for child in node:
            names |= _prove_names_defined(env, names, child)
    return names


def _always_returns(body: tp.Sequence[ast.stmt]) -> bool:
    '''
    Determine if some sequence of statements always reaches a return
    '''
    for stmt in body:
        if isinstance(stmt, ast.Return):
            return True
        elif isinstance(stmt, ast.If):
            if _always_returns(stmt.body) and _always_returns(stmt.orelse):
                return True

    return False


def _never_returns(body: tp.Sequence[ast.stmt]) -> bool:
    '''
    Determine if some sequence of statements never reaches a return
    '''
    for stmt in body:
        if isinstance(stmt, ast.Return):
            return False
        elif isinstance(stmt, ast.If):
            if not (_never_returns(stmt.body) and _never_returns(stmt.orelse)):
                return False

    return True


def _fold_conditions(
        condition_seq: tp.Sequence[tp.Tuple[tp.List[ast.expr], ast.expr]]) -> ast.expr:
    '''
    "Fold" ifExpr over a Sequence of conditons and exprs
    '''
    assert condition_seq
    conditions, expr = condition_seq[0]
    if not conditions or len(condition_seq) == 1:
        return expr
    else:
        conditional = ast.IfExp(
            test=ast.BoolOp(
                op=ast.And(),
                values=conditions,
            ),
            body=expr,
            orelse=_fold_conditions(condition_seq[1:]),
        )
        return conditional


class ssa(Pass):
    '''
    Pass to convert a function to SSA form
    arguments:
        strict: bool
            if strict is True (default) the function must provably always
            reach a return and all names must be defined in all control paths.
            No path feasibility analysis is performed so an exhaustive if over
            cases that ends with a elif will not be recognized for example:
            ```
            def foo(cond: bool):
                if cond:
                    x = 0
                elif not cond:
                    x = 1
                return x
            ```
            would error as x is not provably defined at the return. As the
            normal transformation would result in:
            ```
            def foo(cond: bool):
                x0 = 0
                x1 = 1
                x2 = x0 if cond else 1 if not cond else <?UNDEFINED?>
                __return_value = x2
                return __return_value
            ```
            Note: that a path that would result in x2 being undefined
            corresponds with a path that would normally result in a NameError.

            If strict is set to False it is assumed that the code cannot
            NameError and always reaches a return.  So when a value would be
            conditionally undefined it will just assume such a state cannot
            be reached.  So the previous would be transformed to:
            ```
            def foo(cond: bool):
                x0 = 0
                x1 = 1
                x2 = x0 if cond else 1
                __return_value = x2
                return __return_value
            ```

        return_prefix: str
            Controls the name of the return value. Has no functional effects
            as the pass will only ever use free names.
    '''
    def __init__(self,
            strict: bool = True,
            return_prefix: str = '__return_value'):
        self.strict = strict
        self.return_prefix = return_prefix

    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:
        if not isinstance(tree, ast.FunctionDef):
            raise TypeError('ssa should only be applied to functions')

        # Going to use this in an assert later but need to get the info
        # before any transformation happens
        NR = _never_returns(tree.body)

        # Find all attributes that are written
        targets = collect_targets(tree, ast.Attribute)
        replacer = AttrReplacer({})
        init_reads = []
        id_to_attr = {}
        attr_to_name = {}

        for t in targets:
            i_t = immutable(t)
            if not isinstance(t.value, ast.Name):
                raise NotImplementedError(f'Only supports writing attributes '
                                          f'of Name not {type(t.value)}')
            elif i_t not in attr_to_name:
                name = ast.Name(
                        id=gen_free_name(tree, env, '_'.join((t.value.id, t.attr))),
                        ctx=ast.Store())
                # store the maping of names to attrs
                id_to_attr[name.id] = t
                attr_to_name[i_t] = name
                #replace writes to the attr with writes to the name
                replacer.add_replacement(t, name)
                #replace reads to the attr with reads to the name
                replacer.add_replacement(_flip_ctx(t), _flip_ctx(name))

                # read the init value
                init_reads.append(
                    immutable(ast.Assign(
                        targets=[deepcopy(name)],
                        value=_flip_ctx(t),
                        type_comment=None,
                    ))
                )
            else:
                name = attr_to_name[i_t]
                replacer.add_replacement(t, name)
                replacer.add_replacement(_flip_ctx(t), _flip_ctx(name))



        # Replace references to the attr with the name generated above
        tree = replacer.visit(tree)

        # insert initial reads
        tree.body = [mutable(r) for r in init_reads] + tree.body

        # Perform ssa
        r_name = gen_free_prefix(tree, env, self.return_prefix)
        visitor = SSATransformer(env, r_name, id_to_attr.keys(), self.strict)
        tree = visitor.visit(tree)

        #insert the write backs to the attrs
        for name, conditons in visitor.attr_states.items():
            if conditons:
                tree.body.append(
                    ast.Assign(
                        targets=[deepcopy(id_to_attr[name])],
                        value=_fold_conditions(conditons)
                    )
                )
            else:
                tree.body.append(
                    ast.Assign(
                        targets=[deepcopy(id_to_attr[name])],
                        value=ast.Name(visitor.name_table[name], ast.Load())
                    )
                )

        # insert the return
        if visitor.returns:
            tree.body.append(
                ast.Return(
                    value=_fold_conditions(visitor.returns)
                )
            )
        else:
            assert NR
        return tree, env, metadata

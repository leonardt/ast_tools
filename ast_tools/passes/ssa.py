import ast
from collections import ChainMap, Counter
import itertools
import warnings
import weakref
import typing as tp

import astor

from . import Pass
from . import _PASS_ARGS_T
from ast_tools.stack import SymbolTable

__ALL__ = ['ssa']

class SSATransformer(ast.NodeTransformer):
    def __init__(self, env, return_value_prefx):
        self.env = env
        self.name_idx = Counter()
        self.name_table = ChainMap()
        self.root = None
        self.cond_stack = []
        self.return_value_prefx = return_value_prefx
        self.returns = []


    def _make_name(self, name):
        new_name = name + str(self.name_idx[name])
        self.name_idx[name] += 1
        self.name_table[name] = new_name
        return new_name

    def _make_return(self):
        p = self.return_value_prefx
        name = p + str(self.name_idx[p])
        self.name_idx[p] += 1
        return name

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
            _prove_names_defined(self.env, self.name_table.keys(), node.body)
            if not _always_returns(node.body):
                raise SyntaxError(f'Cannot prove {node.id} returns')
            return super().generic_visit(node)
        else:
            return super().visit(node)

    def visit_If(self, node: ast.If) -> tp.List[ast.stmt]:
        test = self.visit(node.test)
        nt = self.name_table
        suite = []

        self.name_table = t_nt = nt.new_child()
        self.cond_stack.append(test)

        for child in node.body:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, tp.Sequence):
                suite.extend(child)
            else:
                suite.append(child)

        self.name_table = f_nt = nt.new_child()
        self.cond_stack.pop()

        for child in node.orelse:
            child = self.visit(child)
            if child is None:
                continue
            elif isinstance(child, tp.Sequence):
                suite.extend(child)
            else:
                suite.append(child)

        self.name_table = nt

        for name in nt.keys() | t_nt.maps[0].keys() | f_nt.maps[0].keys():
            case0 = name in nt.keys()
            case1 = name in t_nt.maps[0]
            case2 = name in f_nt.maps[0]
            if case0:
                t_name = f_name = ast.Name(
                    id=nt[name],
                    ctx=ast.Load(),
                )
            if case1:
                t_name=ast.Name(
                    id=t_nt[name],
                    ctx=ast.Load(),
                )
            if case2:
                f_name=ast.Name(
                    id=f_nt[name],
                    ctx=ast.Load(),
                )

            # if either the name was introduced in both branches
            # or it was already introduced and modified in one or both
            # mux the name
            if sum((case0, case1, case2)) >= 2:
                suite.append(
                    ast.Assign(
                        targets=[
                            ast.Name(
                                id=self._make_name(name),
                                ctx=ast.Store(),
                            ),
                        ],
                        value=ast.IfExp(
                            test=test,
                            body=t_name,
                            orelse=f_name,
                        )
                    )
                )

        return suite


    def visit_Name(self, node: ast.Name) -> ast.Name:
        name = node.id
        ctx = node.ctx
        if isinstance(ctx, ast.Load):
            return ast.Name(
                    id=self.name_table.setdefault(name, name),
                    ctx=ctx)
        else:
            return ast.Name(
                    id=self._make_name(name),
                    ctx=ctx)

    def visit_Return(self, node: ast.Return) -> ast.Assign:
        r_val = node.value
        r_name = self._make_return()
        self.returns.append((list(self.cond_stack), r_name))
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

    # don't recurs into defs
    def visit_ClassDef(self, node: ast.ClassDef):
        #TODO call renamer
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        #TODO call renamer
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        #TODO call renamer
        return node

def _prove_names_defined(
        env: SymbolTable,
        names: tp.AbstractSet[str],
        node: tp.Union[ast.AST, tp.Sequence[ast.AST]]) -> tp.AbstractSet[str]:
    names = set(names)
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif node.id not in names and node.id not in env:
            if hasattr(node, 'lineno'):
                raise SyntaxError(f'Cannot prove name, {node.id}, is defined at line {node.lineno}')
            else:
                raise SyntaxError(f'Cannot prove name, {node.id}, is defined')

    elif isinstance(node, ast.If):
        t_returns = _always_returns(node.body)
        f_returns = _always_returns(node.orelse)
        if not (t_returns or f_returns):
            t_names = _prove_names_defined(env, names, node.body)
            f_names = _prove_names_defined(env, names, node.orelse)
            names |= t_names & f_names
        elif t_returns:
            names |= _prove_names_defined(env, names, node.orelse)
        elif f_returns:
            names |= _prove_names_defined(env, names, node.body)

    elif isinstance(node, ast.AST):
        for child in ast.iter_child_nodes(node):
            names |= _prove_names_defined(env, names, child)
    else:
        assert isinstance(node, tp.Sequence)
        for child in node:
            names |= _prove_names_defined(env, names, child)
    return names

def _always_returns(body: tp.Sequence[ast.stmt]) -> bool:
    for stmt in body:
        if isinstance(stmt, ast.Return):
            return True
        elif isinstance(stmt, ast.If):
            if _always_returns(stmt.body) and _always_returns(stmt.orelse):
                return True

    return False

def _build_return(
        returns: tp.Sequence[tp.Tuple[tp.List[ast.expr], str]]) -> ast.expr:
    assert returns
    conditions, name = returns[0]
    name = ast.Name(id=name, ctx=ast.Load())
    if not conditions:
        return name
    else:
        assert len(returns) >= 1
        expr = ast.IfExp(
            test=ast.BoolOp(
                op=ast.And(),
                values=conditions,
            ),
            body=name,
            orelse=_build_return(returns[1:]),
        )
        return expr

class ssa(Pass):
    def rewrite(self, tree: ast.AST, env: SymbolTable):
        if not isinstance(tree, ast.FunctionDef):
            raise TypeError('ssa should only be applied to functions')
        r_name = '__return_value'
        visitor = SSATransformer(env, r_name)
        tree = visitor.visit(tree)
        tree.body.append(
            ast.Return(
                value=_build_return(visitor.returns)
            )
        )
        return tree, env


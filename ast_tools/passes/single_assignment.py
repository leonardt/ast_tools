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

__ALL__ = ['single_assignment']

class SingleAssign(ast.NodeTransformer):
    def __init__(self, env):
        self.env = env
        self.name_idx = Counter()
        self.name_table = ChainMap()
        self.root = None

    def _make_name(self, name):
        new_name = name + str(self.name_idx[name])
        self.name_idx[name] += 1
        self.name_table[name] = new_name
        return new_name

    def visit(self, node: ast.AST):
        # basically want to able to visit a top level function
        # but don't want to generally recurse into them
        if self.root is None:
            self.root = node
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    arg_name = arg.arg
                    self.name_table[arg_name] = arg_name
            _prove_names_defined(self.env, set(self.name_table.keys()), [node])
            return super().generic_visit(node)
        else:
            return super().visit(node)

    def visit_If(self, node: ast.If):
        test = self.visit(node.test)

        nt = self.name_table

        self.name_table = t_nt = nt.new_child()
        main = []

        for n in node.body:
            n = self.visit(n)
            if n is None:
                continue
            elif isinstance(n, tp.Sequence):
                main.extend(n)
            else:
                main.append(n)

        self.name_table = f_nt = nt.new_child()

        for n in node.orelse:
            n = self.visit(n)
            if n is None:
                continue
            elif isinstance(n, tp.Sequence):
                main.extend(n)
            else:
                main.append(n)

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
                main.append(
                    ast.Assign(
                        targets=[
                            ast.Name(
                                id=self._make_name(name),
                                ctx=ast.Load(),
                            ),
                        ],
                        value=ast.IfExp(
                            test=test,
                            body=t_name,
                            orelse=f_name,
                        )
                    )
                )

        return main


    def visit_Name(self, node: ast.Name):
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
        names: tp.MutableSet[str],
        body: tp.Sequence[ast.stmt]) -> bool:
    for stmt in body:
        if isinstance(stmt, ast.Name):
            if isinstance(stmt.ctx, ast.Store):
                names.add(stmt.id)
            elif stmt.id not in names and stmt.id not in env:
                raise SyntaxError(f'Cannot prove name, {stmt.id}, is defined at line {stmt.lineno}')
        elif isinstance(stmt, ast.If):
            t_names = set(names)
            f_names = set(names)
            _prove_names_defined(env, t_names, stmt.body)
            _prove_names_defined(env, f_names, stmt.body)
            names.update(t_names & f_names)
        else:
            _prove_names_defined(env, names, ast.iter_child_nodes(stmt))


class single_assignment(Pass):
    def rewrite(self, tree: ast.AST, env: SymbolTable):
        visitor = SingleAssign(env)
        tree = visitor.visit(tree)
        return tree, env


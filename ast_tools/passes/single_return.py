import ast
from itertools import count
import warnings
import weakref
import typing as tp

import astor

from . import Pass
from . import _PASS_ARGS_T
from ast_tools.stack import SymbolTable

__ALL__ = ['single_return']


class ReturnMover(ast.NodeTransformer):
    """
    Moves all returns to the end of the function
    """

    def __init__(self,
            return_value_prefx: str,
            ):
        self.returns = self.ptr = []
        self.r_val_idx = count()
        self.return_value_prefx = return_value_prefx

    def visit_If(self, node: ast.If):
        test = node.test
        ptr = self.ptr
        ptr.append(ast.If(test, [], []))

        self.ptr = ptr[-1].body
        body = []
        for child in node.body:
            child = self.visit(child)
            if child is not None:
                body.append(child)

        self.ptr = ptr[-1].orelse
        orelse = []
        for child in node.orelse:
            child = self.visit(child)
            if child is not None:
                orelse.append(child)

        self.ptr = ptr
        return ast.If(test=test, body=body, orelse=orelse)

    def visit_Return(self, node: ast.Return):
        r_val = node.value
        r_name = self.return_value_prefx + str(next(self.r_val_idx))
        self.ptr.append(
            ast.Assign(
                targets=[ast.Name(id=self.return_value_prefx, ctx=ast.Store())],
                value=ast.Name(id=r_name, ctx=ast.Load())
            )
        )
        return ast.Assign(
            targets=[ast.Name(r_name, ast.Store())],
            value=r_val,
        )

    # don't recurs into defs
    def visit_ClassDef(self, node: ast.ClassDef):
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return node

def _prove_return(body: tp.Sequence[ast.stmt]):
    for stmt in body:
        if isinstance(stmt, ast.Return):
            return True
        elif isinstance(stmt, ast.If):
            if _prove_return(stmt.body) and _prove_return(stmt.orelse):
                return True
    return False

class single_return(Pass):
    def __init__(self, prove_returns: bool = False):
        self.prove_returns = prove_returns

    def rewrite(self, tree: ast.FunctionDef, env: SymbolTable):
        if not isinstance(tree, ast.FunctionDef):
            raise TypeError('single_return should only be applied to functions')
        if not _prove_return(tree.body):
            if self.prove_returns:
                raise SyntaxError(f'Cannot prove that {tree.name} returns')
            else:
                warnings.warn(f'Cannot prove that {tree.name} returns')

        r_name = '__return_value'
        visitor = ReturnMover(r_name)
        tree = visitor.visit(tree)
        tree.body.extend(visitor.returns)
        tree.body.append(
            ast.Return(
                ast.Name(id=r_name, ctx=ast.Load())
            )
        )
        return tree, env

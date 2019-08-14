import ast
from itertools import count
import warnings
import typing as tp

import astor

from . import Pass
from . import _PASS_ARGS_T
from ast_tools.stack import SymbolTable


class ReturnMover(ast.NodeTransformer):
    """
    Moves all returns to the end of the function
    """

    def __init__(self,
            return_value_prefx: str = '__return_value',
            use_bool_ops: bool = True, #controls whether to use not, and or ~, &
            ):
        self.cond_stack = []
        self.returns = []
        self.r_val_idx = count()
        self.return_value_prefx = return_value_prefx
        self.use_bool_ops = use_bool_ops
        if use_bool_ops:
            self.not_ = ast.Not
        else:
            self.not_ = ast.Invert
        self.root = None

    def visit(self, node: ast.FunctionDef):
        if self.root is None:
            if not isinstance(node, ast.FunctionDef):
                raise TypeError(f'ReturnMover expects a FunctionDef not a {type(node)}')
            self.root = node
            func = self.generic_visit(node)
            return func

        else:
            return super().visit(node)

    def visit_If(self, node: ast.If):
        test = node.test
        body = []
        orelse = []

        self.cond_stack.append(test)
        for child in node.body:
            child = self.visit(child)
            if child is not None:
                body.append(child)

        self.cond_stack.pop()
        self.cond_stack.append(ast.UnaryOp(op=self.not_(), operand=test))
        for child in node.orelse:
            child = self.visit(child)
            if child is not None:
                orelse.append(child)

        self.cond_stack.pop()
        return ast.If(test=test, body=body, orelse=orelse)

    def visit_Return(self, node: ast.Return):
        r_val = node.value
        r_name = self.return_value_prefx + str(next(self.r_val_idx))
        self.returns.append((self._reduce_cond_stack(), r_name))
        return ast.Assign(
            targets=[ast.Name(r_name, ast.Store())],
            value=r_val,
        )

    def _reduce_cond_stack(self) -> ast.expr:
        if len(self.cond_stack) == 0:
            return ast.NameConstant(True)
        elif len(self.cond_stack) == 1:
            return self.cond_stack[0]
        elif self.use_bool_ops:
            return ast.BoolOp(ast.And(), list(self.cond_stack))
        else:
            cond = self.cond_stack[0]
            for c in self.cond_stack[1:]:
                cond = ast.BoolOp(cond, ast.BitAnd(), c)
            return cond

    # don't recurs into defs
    def visit_ClassDef(self, node: ast.ClassDef):
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return node

class single_return(Pass):
    def rewrite(self, tree, env):
        visitor = ReturnMover()
        tree = visitor.visit(tree)
        if len(visitor.returns) == 0:
            return tree
        orelse = None
        for cond, r_val in reversed(visitor.returns):
            if_ = ast.If(
                test=cond,
                body=[
                    ast.Assign(
                        targets=[ast.Name(id=visitor.return_value_prefx, ctx=ast.Store())],
                        value=ast.Name(id=r_val, ctx=ast.Load())
                    )
                ]
            )
            if orelse is None:
                if_.orelse = []
            else:
                if_.orelse = [orelse]
            orelse = if_

        assert orelse is not None
        tree.body.append(orelse)
        tree.body.append(
            ast.Return(
                value=ast.Name(id=visitor.return_value_prefx, ctx=ast.Load())
            )
        )
        return tree, env

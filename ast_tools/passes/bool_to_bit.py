import ast
import typing as tp

from . import Pass
from . import PASS_ARGS_T

from ast_tools.stack import SymbolTable

__ALL__ = ['bool_to_bit']

class BoolOpTransformer(ast.NodeTransformer):
    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        # Can't get more specific on return type because if
        # len(node.values) == 1 (which it shouldn't be)
        # then the return type is expr otherwise
        # the return type is Union[BinOp, BoolOp]

        if isinstance(node.op, self.match):
            values = node.values
            assert values # should not be empty
            expr = self.visit(values[0])
            for v in map(self.visit, values[1:]):
                expr = ast.BinOp(expr, self.replace(), v)
            return expr
        else:
            return self.generic_visit(node)


class AndTransformer(BoolOpTransformer):
    match = ast.And
    replace = ast.BitAnd


class OrTransformer(BoolOpTransformer):
    match = ast.Or
    replace = ast.BitOr


class NotTransformer(ast.NodeTransformer):
    def visit_Not(self, node: ast.Not) -> ast.Invert:
        return ast.Invert()


class bool_to_bit(Pass):
    '''
    Pass to replace bool operators (and, or, not)
    with bit operators (&, |, ~)
    '''
    def __init__(self,
            replace_and: bool = True,
            replace_or:  bool = True,
            replace_not: bool = True,
            ):
        self.replace_and = replace_and
        self.replace_or = replace_or
        self.replace_not = replace_not

    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:
        if self.replace_and:
            visitor = AndTransformer()
            tree = visitor.visit(tree)

        if self.replace_or:
            visitor = OrTransformer()
            tree = visitor.visit(tree)

        if self.replace_not:
            visitor = NotTransformer()
            tree = visitor.visit(tree)

        return tree, env, metadata

import typing as tp

import libcst as cst

from . import Pass
from . import PASS_ARGS_T

from ast_tools.stack import SymbolTable

__ALL__ = ['bool_to_bit']

class BoolOpTransformer(cst.CSTTransformer):
    match: tp.Union[
            tp.Sequence[tp.Type[cst.BaseBooleanOp]],
            tp.Type[cst.BaseBooleanOp],
    ]

    replace: tp.Type[cst.BaseBinaryOp]

    def leave_BooleanOperation(
            self,
            original_node: cst.BooleanOperation,
            updated_node: cst.BooleanOperation) -> cst.BinaryOperation:
        if isinstance(updated_node.operator, self.match):
            return cst.BinaryOperation(
                    left=updated_node.left,
                    operator=self.replace(),
                    right=updated_node.right,
                    lpar=updated_node.lpar,
                    rpar=updated_node.rpar
                )
        else:
            return updated_node


class AndTransformer(BoolOpTransformer):
    match = cst.And
    replace = cst.BitAnd


class OrTransformer(BoolOpTransformer):
    match = cst.Or
    replace = cst.BitOr


class NotTransformer(cst.CSTTransformer):
    def leave_Not(
            self,
            original_node: cst.Not,
            updated_node: cst.Not) -> cst.BitInvert:
        return cst.BitInvert()


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
            tree: cst.CSTNode,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:
        if self.replace_and:
            visitor = AndTransformer()
            tree = tree.visit(visitor)

        if self.replace_or:
            visitor = OrTransformer()
            tree = tree.visit(visitor)

        if self.replace_not:
            visitor = NotTransformer()
            tree = tree.visit(visitor)

        return tree, env, metadata

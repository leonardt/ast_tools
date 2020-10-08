import typing as tp

import libcst as cst

from .insert_statements import InsertStatementsVisitor

_T = tp.Union[
        cst.BaseSuite,
        cst.BaseExpression,
        cst.BaseStatement,
        cst.BaseSmallStatement,
        cst.Module,
]
def to_module(node: _T) -> cst.Module:
    if isinstance(node, cst.SimpleStatementSuite):
        return cst.Module(body=node.body)
    elif isinstance(node, cst.IndentedBlock):
        return cst.Module(body=node.body)

    if isinstance(node, cst.BaseExpression):
        node = cst.Expr(value=node)

    if isinstance(node, (cst.BaseStatement, cst.BaseSmallStatement)):
        node = cst.Module(body=(node,))

    if isinstance(node, cst.Module):
        return node

    raise TypeError(f'{node} :: {type(node)} cannot be cast to Module')

class DeepNode:
    node: cst.CSTNode

    def __init__(self, node: cst.CSTNode):
        self.node = node

    def __eq__(self, other: 'DeepNode') -> bool:
        if isinstance(other, DeepNode):
            return self.node.deep_equals(other.node)
        else:
            return NotImplemented

    def __ne__(self, other: 'DeepNode') -> bool:
        if isinstance(other, DeepNode):
            return not self.node.deep_equals(other.node)
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return hash(self.node)

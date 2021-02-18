import typing as tp

import libcst as cst

from .insert_statements import InsertStatementsVisitor
from .deep_node import DeepNode


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

def to_stmt(node: cst.BaseSmallStatement) -> cst.SimpleStatementLine:
    return cst.SimpleStatementLine(body=[node])

def make_assign(
        lhs: cst.BaseAssignTargetExpression,
        rhs: cst.BaseExpression,
        ) -> cst.Assign:
    return cst.Assign(
        targets=[cst.AssignTarget(lhs),],
        value=rhs,
    )

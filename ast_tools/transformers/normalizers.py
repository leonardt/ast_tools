import typing as tp

import libcst as cst
import libcst.matchers as m

from ast_tools.cst_utils import to_stmt

class ElifToElse(m.MatcherDecoratableTransformer):
    @m.leave(m.If(orelse=m.If()))
    def _(self,
            original_node: cst.If,
            updated_node: cst.If,
            ) -> cst.If:
        orelse = cst.Else(
            body=cst.IndentedBlock(
                body=[updated_node.orelse]
            )
        )
        updated_node = updated_node.with_changes(orelse=orelse)
        return updated_node


class NormalizeBlocks(cst.CSTTransformer):
    def leave_SimpleStatementSuite(self,
            original_node: cst.SimpleStatementSuite,
            updated_node: cst.SimpleStatementSuite,
            ) -> cst.IndentedBlock:
        body = tuple(to_stmt(stmt) for stmt in updated_node.body)
        return cst.IndentedBlock(
            body=body
        ).visit(self)


class NormalizeLines(NormalizeBlocks):
    def _normalize_body(self,
            updated_node: tp.Union[cst.IndentedBlock, cst.Module]):
        body = []
        for node in updated_node.body:
            if isinstance(node, cst.SimpleStatementLine):
                body.extend(map(to_stmt, node.body))
            else:
                body.append(node)
        return updated_node.with_changes(body=body)

    def leave_IndentedBlock(self,
            original_node: cst.IndentedBlock,
            updated_node: cst.IndentedBlock,
            ) -> cst.IndentedBlock:
        return self._normalize_body(updated_node)

    def leave_Module(self,
            original_node: cst.Module,
            updated_node: cst.Module
            ) -> cst.Module:
        return self._normalize_body(updated_node)

    def leave_SimpleStatementSuite(self,
            original_node: cst.SimpleStatementSuite,
            updated_node: cst.SimpleStatementSuite,
            ) ->  tp.Union[cst.SimpleStatementSuite, cst.IndentedBlock]:
        # Only transform to IndentedBlock if node contains more than 1 statement
        if len(updated_node.body) > 1:
            return super().leave_SimpleStatementSuite(
                    original_node, updated_node)
        return updated_node


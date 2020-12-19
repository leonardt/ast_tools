import typing as tp

import libcst as cst

class AlwaysReturnsProvider(cst.BatchableMetadataProvider[bool]):
    def _visit_simple_block(self,
            node: tp.Union[cst.SimpleStatementLine, cst.SimpleStatementSuite]
            ) -> tp.Optional[bool]:
        for child in node.body:
            if isinstance(child, cst.Return):
                self.set_metadata(node, True)
                return False
        self.set_metadata(node, False)
        return False

    def visit_SimpleStatementLine(self,
            node: cst.SimpleStatementLine,
            ) -> tp.Optional[bool]:
        return self._visit_simple_block(node)

    def visit_SimpleStatementSuite(self,
            node: cst.SimpleStatementLine,
            ) -> tp.Optional[bool]:
        return self._visit_simple_block(node)

    def leave_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        for child in node.body:
            if self.get_metadata(type(self), child, False):
                self.set_metadata(node, True)
                return
        self.set_metadata(node, False)

    def leave_If(self, node: cst.If) -> None:
        if node.orelse is None:
            self.set_metadata(node, False)
        else:
            self.set_metadata(node,
                self.get_metadata(type(self), node.body, False)
                and self.get_metadata(type(self), node.orelse, False))

    def leave_Else(self, node: cst.Else) -> None:
        self.set_metadata(node, self.get_metadata(type(self), node.body, False))


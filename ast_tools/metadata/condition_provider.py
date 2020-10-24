import typing as tp

import libcst as cst

class ConditionProvider(cst.VisitorMetadataProvider):
    '''
    Marks each  node with the conditions underwhich they will be executed
    '''
    cond_stack: tp.List[cst.BaseExpression]

    def __init__(self):
        self.cond_stack = []

    def on_leave(self, node: cst.CSTNode) -> None:
        self.set_metadata(node, tuple(self.cond_stack))
        return super().on_leave(node)

    def visit_If_body(self, node: cst.If) -> None:
        self.cond_stack.append(node.test)

    def leave_If_body(self, node: cst.If) -> None:
        self.cond_stack.pop()

    def visit_If_orelse(self, node: cst.If) -> None:
        self.cond_stack.append(cst.UnaryOperation(cst.Not(), node.test))

    def leave_If_orelse(self, node: cst.If) -> None:
        self.cond_stack.pop()

    def visit_IfExp_body(self, node: cst.IfExp) -> None:
        self.cond_stack.append(node.test)

    def leave_IfExp_body(self, node: cst.If) -> None:
        self.cond_stack.pop()

    def visit_IfExp_orelse(self, node: cst.IfExp) -> None:
        self.cond_stack.append(cst.UnaryOperation(cst.Not(), node.test))

    def leave_IfExp_orelse(self, node: cst.IfExp) -> None:
        self.cond_stack.pop()


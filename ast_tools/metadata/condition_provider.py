import typing as tp

import libcst as cst

from . import AlwaysReturnsProvider


class ConditionProvider(cst.VisitorMetadataProvider):
    '''
    Marks each  node with the conditions under which they will be executed
    '''
    cond_stack: tp.List[cst.BaseExpression]

    def __init__(self, simplify: bool = False):
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


class IncrementalConditionProvider(ConditionProvider):
    '''
    Condition provider which implicitly negates previous conditions if
    they are not explicitly listed.  Used in SSA to generate a "minimal"
    ite structures.

    Consider:
        ```
        if x:
            return 0
        else:
            return 1
        return 2
        ```
    using the normal ConditonProvider ssa would generate the following:
        ```
        return 0 if x else (1 if not x else 2)
        ```
    However, do the structure of the program we can see that this can be
    simplified to:
        ```
        return 0 if x else 1
        ```
    '''

    METADATA_DEPENDENCIES = (AlwaysReturnsProvider,)


    def visit_If_orelse(self, node: cst.If) -> None:
        if not self.get_metadata(AlwaysReturnsProvider, node.body):
            super().visit_If_orelse(node)

    def leave_If_orelse(self, node: cst.If) -> None:
        if not self.get_metadata(AlwaysReturnsProvider, node.body):
            super().leave_If_orelse(node)

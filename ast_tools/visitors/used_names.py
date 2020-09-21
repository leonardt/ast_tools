from functools import lru_cache
import typing as tp

import libcst as cst

class UsedNames(cst.CSTVisitor):
    def __init__(self):
        self.names: tp.MutableSet[str] = set()

    def visit_Name(self, node: cst.Name):
        self.names.add(node.value)

@lru_cache()
def used_names(tree: cst.CSTNode):
    visitor = UsedNames()
    tree.visit(visitor)
    return visitor.names

from functools import lru_cache
import typing as tp

import libcst as cst
from libcst.metadata import ScopeProvider

from ast_tools.cst_utils import to_module

class UsedNames(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (ScopeProvider,)

    def __init__(self):
        super().__init__()
        self.names: tp.MutableSet[str] = set()
        self.scope: tp.Optional[cst.metadata.Scope] = None

    def on_visit(self, node: cst.CSTNode):
        if self.scope is None:
            self.scope = self.get_metadata(ScopeProvider, node)

        return super().on_visit(node)


    def visit_Name(self, node: cst.Name):
        if node in self.scope.assignments:
            self.names.add(node.value)

@lru_cache()
def used_names(tree: cst.CSTNode):
    tree = to_module(tree)
    visitor = UsedNames()
    wrapper = cst.MetadataWrapper(tree, unsafe_skip_copy=True)
    wrapper.visit(visitor)
    return visitor.names

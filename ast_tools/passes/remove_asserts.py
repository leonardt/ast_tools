import typing as tp

import libcst as cst

from . import Pass, PASS_ARGS_T
from ast_tools.stack import SymbolTable
from ast_tools.transformers.node_replacer import NodeReplacer

class AssertRemover(NodeReplacer):
    def __init__(self):
        # replace asserts with pass
        super().__init__({cst.Assert: cst.Pass()})

    def _get_key(self, node): return type(node)


class remove_asserts(Pass):
    def rewrite(self,
            tree: cst.CSTNode,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        visitor = AssertRemover()
        tree =  tree.visit(visitor)
        return tree, env, metadata


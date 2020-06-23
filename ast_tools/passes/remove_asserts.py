import ast
import typing as tp

from . import Pass, PASS_ARGS_T
from ast_tools.stack import SymbolTable
from ast_tools.transformers.node_replacer import NodeReplacer

class AssertRemover(NodeReplacer):
    def __init__(self):
        # replace asserts with pass
        super().__init__({ast.Assert: ast.Pass()})

    def _get_key(self, node): return type(node)


class remove_asserts(Pass):
    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        visitor = AssertRemover()
        tree =  visitor.visit(tree)
        return tree, env, metadata


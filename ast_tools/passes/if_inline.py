import ast
import typing as tp

from ast_tools.stack import SymbolTable
from . import Pass, PASS_ARGS_T
from ast_tools.transformers.if_inliner import inline_ifs


class if_inline(Pass):
    def rewrite(self,
                tree: ast.AST,
                env: SymbolTable,
                metadata: tp.MutableMapping) -> PASS_ARGS_T:
        return inline_ifs(tree, env), env, metadata

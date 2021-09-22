import typing as tp

import libcst as cst

from ast_tools.stack import SymbolTable
from . import Pass, PASS_ARGS_T
from ast_tools.transformers.if_inliner import inline_ifs
from ast_tools.transformers.normalizers import ElifToElse


class if_inline(Pass):
    def rewrite(self,
                tree: cst.CSTNode,
                env: SymbolTable,
                metadata: tp.MutableMapping) -> PASS_ARGS_T:
        return inline_ifs(tree, env), env, metadata

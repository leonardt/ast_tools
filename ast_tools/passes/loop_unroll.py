import typing as tp

import libcst as cst

from ast_tools.stack import SymbolTable
from . import Pass, PASS_ARGS_T
from ast_tools.transformers.loop_unroller import unroll_for_loops


class loop_unroll(Pass):
    def rewrite(self,
                tree: cst.CSTNode,
                env: SymbolTable,
                metadata: tp.MutableMapping) -> PASS_ARGS_T:
        return unroll_for_loops(tree, env), env, metadata

import typing as tp

import libcst as cst

from .symbol_replacer import replace_symbols
from ..macros import inline
from ast_tools.cst_utils import to_module

class Inliner(cst.CSTTransformer):
    def __init__(self, env: tp.Mapping[str, tp.Any]):
        super().__init__()
        self.env = env

    def leave_If(
            self,
            original_node: cst.If,
            updated_node: cst.If
            ) -> tp.Union[cst.If, cst.RemovalSentinel, cst.FlattenSentinel[cst.BaseStatement]]:
        try:
            cond_obj = eval(to_module(updated_node.test).code, {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(cond_obj, inline):
            if cond_obj:
                updated_node = cst.FlattenSentinel(updated_node.body.body)
            else:
                orelse = updated_node.orelse
                if orelse is None:
                    updated_node = cst.RemoveFromParent()
                elif isinstance(orelse, cst.If):
                    updated_node = updated_node.orelse
                else:
                    assert isinstance(orelse, cst.Else)
                    updated_node = cst.FlattenSentinel(orelse.body.body)
        return super().leave_If(original_node, updated_node)


def inline_ifs(tree: cst.CSTNode, env: tp.Mapping[str, tp.Any]) -> cst.CSTNode:
    return tree.visit(Inliner(env))

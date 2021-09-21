import typing as tp

import libcst as cst

from .symbol_replacer import replace_symbols
from ..macros import inline
from ast_tools.cst_utils import to_module

class Inliner(cst.CSTTransformer):
    def __init__(self, env: tp.Mapping[str, tp.Any]):
        super().__init__()
        self.env = env

    def visit_If(self, node):
        # Control recursion order.
        # Need to avoid putting an a flatten sentinel in orelse
        # can happen if the elif is being inlined
        return False

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
                new_body = updated_node.body.visit(self)
                updated_node = cst.FlattenSentinel(new_body.body)
            else:
                orelse = updated_node.orelse
                if orelse is None:
                    updated_node = cst.RemoveFromParent()
                elif isinstance(orelse, cst.If):
                    updated_node = updated_node.orelse.visit(self)
                else:
                    assert isinstance(orelse, cst.Else)
                    new_body = updated_node.orelse.body.visit(self)
                    updated_node = cst.FlattenSentinel(new_body.body)
        else:
            new_body = updated_node.body.visit(self)
            if updated_node.orelse:
                new_orelse = updated_node.orelse.visit(self)
            else:
                new_orelse = None

            updated_node = updated_node.with_changes(body=new_body, orelse=new_orelse)

        return super().leave_If(original_node, updated_node)


def inline_ifs(tree: cst.CSTNode, env: tp.Mapping[str, tp.Any]) -> cst.CSTNode:
    return tree.visit(Inliner(env))

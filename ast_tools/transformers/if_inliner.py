import typing as tp

import libcst as cst

from .symbol_replacer import replace_symbols
from ..macros import inline
from ast_tools.cst_utils import to_module, InsertStatementsVisitor

class Inliner(InsertStatementsVisitor):
    def __init__(self, env: tp.Mapping[str, tp.Any]):
        super().__init__(cst.codemod.CodemodContext())
        self.env = env

    def leave_If(
            self,
            original_node: cst.If,
            updated_node: cst.If) -> cst.CSTNode:

        try:
            cond_obj = eval(to_module(updated_node.test).code, {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(cond_obj, inline):
            if cond_obj:
                self.insert_statements_after_current(updated_node.body.body)
                updated_node = cst.RemoveFromParent()
            else:
                orelse = updated_node.orelse
                if orelse is None:
                    updated_node = cst.RemoveFromParent()
                elif isinstance(orelse, cst.If):
                    updated_node = updated_node.orelse
                else:
                    assert isinstance(orelse, cst.Else)
                    self.insert_statements_after_current(orelse.body.body)
                    updated_node = cst.RemoveFromParent()
        return super().leave_If(original_node, updated_node)


def inline_ifs(tree: cst.CSTNode, env: tp.Mapping[str, tp.Any]) -> cst.CSTNode:
    visitor = Inliner(env)
    if isinstance(tree, cst.Module):
        return tree.visit(visitor)
    else:
        new_body = tree.body.visit(visitor)
        return tree.with_changes(body=new_body)

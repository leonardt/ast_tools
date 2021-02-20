import typing as tp

import libcst as cst

from .symbol_replacer import replace_symbols
from ..macros import unroll
from ast_tools.cst_utils import to_module

class Unroller(cst.CSTTransformer):
    def __init__(self, env: tp.Mapping[str, tp.Any]):
        super().__init__()
        self.env = env

    def leave_For(
            self,
            original_node: cst.For,
            updated_node: cst.For) -> tp.Union[cst.For, cst.FlattenSentinel[cst.BaseStatement]]:

        try:
            iter_obj = eval(to_module(updated_node.iter).code, {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(iter_obj, unroll):
            body = []
            if not isinstance(updated_node.target, cst.Name):
                raise NotImplementedError('Unrolling with non-name target')

            for i in iter_obj:
                if isinstance(i, int):
                    symbol_table = {updated_node.target.value: cst.Integer(value=repr(i))}
                    for child in updated_node.body.body:
                        body.append(
                            replace_symbols(child, symbol_table)
                        )
                else:
                    raise NotImplementedError('Unrolling non-int iterator')

            updated_node = cst.FlattenSentinel(body)
        return super().leave_For(original_node, updated_node)


def unroll_for_loops(tree: cst.CSTNode, env: tp.Mapping[str, tp.Any]) -> cst.CSTNode:
    return tree.visit(Unroller(env))

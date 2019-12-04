import ast
from copy import deepcopy
import astor
from .symbol_replacer import replace_symbols
from ..macros import unroll


def is_call(node):
    return isinstance(node, ast.Call)


def is_name(node):
    return isinstance(node, ast.Name)


class Unroller(ast.NodeTransformer):
    def __init__(self, env):
        self.env = env

    def visit_For(self, node):
        node = super().generic_visit(node)
        try:
            iter_obj = eval(astor.to_source(node.iter), {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(iter_obj, unroll):
            body = []
            for i in iter_obj:
                if not isinstance(i, int):
                    raise NotImplementedError("Unrolling over iterator of"
                                              "non-int")
                symbol_table = {node.target.id: ast.Num(i)}
                for child in node.body:
                    body.append(
                        replace_symbols(deepcopy(child), symbol_table)
                    )
            return body
        return node


def unroll_for_loops(tree, env):
    return Unroller(env).visit(tree)

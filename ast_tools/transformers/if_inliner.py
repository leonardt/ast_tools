import ast
from copy import deepcopy
import astor
from .symbol_replacer import replace_symbols
from ..macros import inline


class Inliner(ast.NodeTransformer):
    def __init__(self, env):
        self.env = env

    def visit_If(self, node):
        node = super().generic_visit(node)
        try:
            cond_obj = eval(astor.to_source(node.test), {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(cond_obj, inline):
            if cond_obj:
                return node.body
            else:
                return node.orelse
        return node


def inline_ifs(tree, env):
    return Inliner(env).visit(tree)

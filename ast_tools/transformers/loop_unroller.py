import ast
from copy import deepcopy
import astor
from .symbol_replacer import replace_symbols
from ..macros import RANGE


def is_call(node):
    return isinstance(node, ast.Call)


def is_name(node):
    return isinstance(node, ast.Name)


class Unroller(ast.NodeTransformer):
    def __init__(self, env):
        self.env = env

    def flat_visit(self, body):
        new_body = []
        for statement in body:
            result = self.visit(statement)
            if isinstance(result, list):
                new_body.extend(result)
            else:
                new_body.append(result)
        return new_body

    def visit_For(self, node):
        try:
            range_object = eval(astor.to_source(node.iter), {}, self.env)
            is_constant = True
        except Exception as e:
            is_constant = False
        if is_constant and isinstance(range_object, RANGE):
            body = []
            for i in range_object:
                symbol_table = {node.target.id: ast.Num(i)}
                for child in node.body:
                    body.append(
                        replace_symbols(deepcopy(child), symbol_table)
                    )
            return body
        return super().generic_visit(node)


def unroll_for_loops(tree, env):
    return Unroller(env).visit(tree)

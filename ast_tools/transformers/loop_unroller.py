import ast
from copy import deepcopy
import astor
from .symbol_replacer import replace_symbols


class UnrollException(Exception):
    def __init__(self, execption):
        message = f"Unable to evaluate `unroll_range` object during " \
            f"unrolling pass, got exception {execption}"
        super().__init__(message)


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

    def is_unroll_kwarg(self, keyword):
        return keyword.arg == "unroll" and \
            isinstance(keyword.value, ast.NameConstant) and \
            keyword.value.value is True

    def is_unroll_range(self, node):
        if not is_call(node) and is_name(node.func) and \
                node.func.id == "range":
            return False
        return any(map(self.is_unroll_kwarg, node.keywords))

    def visit_For(self, node):
        if self.is_unroll_range(node.iter):
            node.iter.keywords = list(filter(
                lambda x: not self.is_unroll_kwarg(x),
                node.iter.keywords
            ))
            try:
                range_object = eval(astor.to_source(node.iter), {}, self.env)
            except Exception as e:
                raise UnrollException(e)
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

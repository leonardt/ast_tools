import ast
from copy import deepcopy
import astor


class UnrollException(Exception):
    def __init__(self, execption):
        message = f"Unable to evaluate `unroll_range` object during " \
            f"unrolling pass, got exception {execption}"
        super().__init__(message)


def is_call(node):
    return isinstance(node, ast.Call)


def is_name(node):
    return isinstance(node, ast.Name)


def replace_symbols(tree, symbol_table):
    class SymbolReplacer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in symbol_table:
                return deepcopy(symbol_table[node.id])
            return node
    return SymbolReplacer().visit(tree)


def unroll_for_loops(tree, env):
    class Unroller(ast.NodeTransformer):
        def flat_visit(self, body):
            new_body = []
            for statement in body:
                result = self.visit(statement)
                if isinstance(result, list):
                    new_body.extend(result)
                else:
                    new_body.append(result)
            return new_body

        def visit(self, node):
            """
            For nodes with a `body` attribute, we explicitly traverse them and
            flatten any lists that are returned. This allows visitors to return
            more than one node.
            """
            if not hasattr(node, 'body') or isinstance(node, ast.IfExp):
                return super().visit(node)
            node.body = self.flat_visit(node.body)
            if hasattr(node, 'orelse'):
                node.orelse = self.flat_visit(node.orelse)
            return super().visit(node)

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
                    range_object = eval(astor.to_source(node.iter), {}, env)
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
            return node
    return Unroller().visit(tree)

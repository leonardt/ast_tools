"""
Defines a visitor that collects all calls contained in an AST
"""
import ast

class CallCollector(ast.NodeVisitor):
    def __init__(self):
        self.calls = []

    def visit_Call(self, node: ast.Call):
        self.calls.append(node)


def collect_calls(tree):
    visitor = CallCollector()
    visitor.visit(tree)
    return visitor.calls



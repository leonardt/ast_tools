import ast
from functools import lru_cache

class UsedNames(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Name(self, node: ast.Name):
        self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.names.add(node.name)

@lru_cache()
def used_names(tree: ast.AST):
    visitor = UsedNames()
    visitor.visit(tree)
    return visitor.names

from functools import lru_cache

from ast_tools import immutable_ast as iast

class UsedNames(iast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def visit_Name(self, node: iast.Name):
        self.names.add(node.id)

    def visit_FunctionDef(self, node: iast.FunctionDef):
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: iast.AsyncFunctionDef):
        self.names.add(node.name)

    def visit_ClassDef(self, node: iast.ClassDef):
        self.names.add(node.name)

@lru_cache()
def used_names(tree: iast.AST):
    visitor = UsedNames()
    visitor.visit(tree)
    return visitor.names

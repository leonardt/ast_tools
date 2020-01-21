"""
Defines a visitor that collects all assignment targets contained in an AST
"""
import ast
import functools

def _filt(t):
    def wrapped(obj):
        return isinstance(obj, t)
    return wrapped

class TargetCollector(ast.NodeVisitor):
    def __init__(self, target_filter=None):
        if target_filter is None:
            target_filter = ast.AST
        self.target_filter = _filt(target_filter)
        self.targets = set()

    def visit_Assign(self, node: ast.Assign):
        self.targets.update(filter(self.target_filter, node.targets))


def collect_targets(tree, target_filter=None):
    visitor = TargetCollector(target_filter)
    visitor.visit(tree)
    return visitor.targets



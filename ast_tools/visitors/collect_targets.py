"""
Defines a visitor that collects all assignment targets contained in an AST
"""
import functools

import libcst as cst

def _filt(t):
    def wrapped(obj):
        return isinstance(obj, t)
    return wrapped

class TargetCollector(cst.CSTVisitor):
    def __init__(self, target_filter=None):
        if target_filter is None:
            target_filter = cst.CSTNode
        self.target_filter = _filt(target_filter)
        self.targets = []

    def visit_Assign(self, node: cst.Assign):
        self.targets.extend(filter(self.target_filter, (n.target for n in node.targets)))


def collect_targets(tree, target_filter=None):
    visitor = TargetCollector(target_filter)
    tree.visit(visitor)
    return visitor.targets



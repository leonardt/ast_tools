"""
Defines a visitor that collects all names contained in an AST
"""

import ast


class NameCollector(ast.NodeVisitor):
    """
    Collect all instances of `Name` in an AST
    """

    def __init__(self, ctx=None):
        """
        Set `ctx` to `ast.Store` or `ast.Load` to filter for names that are
        being loaded or stored into
        """
        self.names = set()
        self.ctx = ctx

    def visit_Name(self, node):  # pylint: disable=invalid-name
        """
        If `self.ctx` is None (default), add to set of names, otherwise, check
        if it is an instance of `self.ctx`
        """
        if self.ctx is None or isinstance(node.ctx, self.ctx):
            self.names.add(node.id)


def collect_names(tree, ctx=None):
    """
    Convenience wrapper for NameCollector
    """
    visitor = NameCollector(ctx)
    visitor.visit(tree)
    return visitor.names

import abc
import ast
from copy import deepcopy

class NodeFinder(ast.NodeVisitor, metaclass=abc.ABCMeta):
    def __init__(self, node):
        key = self._get_key(node)
        if key is None:
            raise TypeError(f'Unsupported node {node}')

        self.key = key
        self.target = None

    def visit(self, node):
        if self.target is not None:
            return

        key = self._get_key(node)
        if key is None or key != self.key:
            return super().visit(node)
        else:
            self.target = node

    @abc.abstractmethod
    def _get_key(self, node): pass

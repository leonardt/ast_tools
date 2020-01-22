import abc
import ast
from copy import deepcopy

class NodeReplacer(ast.NodeTransformer, metaclass=abc.ABCMeta):
    def __init__(self, node_table):
        self.node_table = node_table

    def visit(self, node):
        key = self._get_key(node)
        if key is None or key not in self.node_table:
            return super().visit(node)
        else:
            return deepcopy(self.node_table[key])

    def add_replacement(self, node, replacement):
        key = self._get_key(node)
        if key is None:
            raise TypeError(f'Unsupported node {node}')
        self.node_table[key] = replacement

    @abc.abstractmethod
    def _get_key(self, node): pass

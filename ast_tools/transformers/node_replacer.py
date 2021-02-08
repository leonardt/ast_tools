import abc
import typing as tp

import libcst as cst

_NT =  tp.MutableMapping[tp.Any, cst.CSTNode]
class NodeReplacer(cst.CSTTransformer, metaclass=abc.ABCMeta):
    node_table: _NT

    def __init__(self, node_table: tp.Optional[_NT] = None):
        if node_table is None:
            node_table = {}
        self.node_table = node_table

    def on_leave(self,
            original_node: cst.CSTNode,
            updated_node: cst.CSTNode,
            ) -> tp.Union[cst.CSTNode, cst.RemovalSentinel]:
        key = self._get_key(original_node)
        if key is None or key not in self.node_table:
            return super().on_leave(original_node, updated_node)
        else:
            return self.node_table[key]

    def add_replacement(self, node: cst.CSTNode, replacement: cst.CSTNode):
        key = self._get_key(node)
        if key is None:
            raise TypeError(f'Unsupported node {node}')
        self.node_table[key] = replacement

    @abc.abstractmethod
    def _get_key(self, node: cst.CSTNode) -> tp.Hashable: pass

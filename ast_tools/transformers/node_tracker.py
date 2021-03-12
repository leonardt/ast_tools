import functools as ft
import typing as tp
import types
from collections import defaultdict

import libcst as cst
import libcst.matchers as m
from libcst import CSTNode, CSTNodeT, RemovalSentinel, FlattenSentinel


from ast_tools.utils import BiMap

class _NodeTrackerMixin:
    node_tracking_table: BiMap[CSTNode, CSTNode]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.node_tracking_table = BiMap()
        self.new = set()

    def on_leave(self,
            original_node: CSTNodeT,
            updated_node: tp.Union[CSTNodeT, RemovalSentinel, FlattenSentinel[CSTNodeT]]
            ) -> tp.Union[CSTNodeT, RemovalSentinel, FlattenSentinel[CSTNodeT]]:
        final_node = super().on_leave(original_node, updated_node)
        self.track_with_children(original_node, final_node)
        return final_node


    def _track(self,
            original_node: CSTNode,
            updated_node: cst.CSTNode) -> None:
        if original_node in self.node_tracking_table.i:
            # original_node has a origin, track back
            for o_node in self.node_tracking_table.i[original_node]:
                self._track(o_node, updated_node)
            return

        if updated_node in self.node_tracking_table:
            # updated_node is an origin, skip it
            for u_node in self.node_tracking_table[updated_node]:
                self._track(original_node, u_node)
            return
        assert updated_node not in self.node_tracking_table, (original_node, updated_node)
        assert original_node not in self.node_tracking_table.i, (original_node, updated_node)
        self.node_tracking_table[original_node] = updated_node

    def _track_with_children(self,
            original_nodes: tp.Iterable[CSTNode],
            updated_nodes: tp.Iterable[CSTNode]) -> None:

        for o_node in original_nodes:
            for u_node in updated_nodes:
                if u_node not in self.node_tracking_table.i or u_node in self.new:
                    # u_node has not been explained or has multiple origins
                    self.new.add(u_node)
                    self._track(o_node, u_node)
                    self._track_with_children(original_nodes, u_node.children)

    def track(self,
            original_node: tp.Union[CSTNode, tp.Iterable[CSTNode]],
            updated_node: tp.Union[CSTNode, RemovalSentinel, tp.Iterable[CSTNode]]) -> None:

        if isinstance(updated_node, CSTNode):
            updated_node = updated_node,

        if isinstance(updated_node, RemovalSentinel) or not updated_node:
            return

        if isinstance(original_node, CSTNode):
            original_node = original_node,

        for o_node in original_nodes:
            for u_node in updated_nodes:
                self._track(o_node, u_node)


    def track_with_children(self,
            original_node: tp.Union[CSTNode, tp.Iterable[CSTNode]],
            updated_node: tp.Union[CSTNode, RemovalSentinel, tp.Iterable[CSTNode]]) -> None:

        if isinstance(updated_node, CSTNode):
            updated_node = updated_node,

        if isinstance(updated_node, RemovalSentinel) or not updated_node:
            return

        if isinstance(original_node, CSTNode):
            original_node = original_node,

        self._track_with_children(original_node, updated_node)
        self.new = set()

    def trace_origins(self, prev_table: BiMap[CSTNode, CSTNode]) -> BiMap[CSTNode, CSTNode]:
        new_table = BiMap()
        for update, origins in self.node_tracking_table.i.items():
            for o in origins:
                for oo in prev_table.i.get(o, []):
                    new_table[oo] = update

        for origin, updates in prev_table.items():
            for u in updates:
                for uu in self.node_tracking_table.get(u, [u]):
                    new_table[origin] = uu


        return new_table


class NodeTrackingTransformer(
        _NodeTrackerMixin,
        cst.CSTTransformer): pass


class NodeTrackingMatcherTransformer(
        _NodeTrackerMixin,
        m.MatcherDecoratableTransformer): pass


def with_tracking(transformer: tp.Type[cst.CSTTransformer]) -> tp.Type[cst.CSTTransformer]:
    """ Helper function than adds tracking to a transformer type """
    return type(transformer.__name__, (_NodeTrackerMixin, transformer), {})

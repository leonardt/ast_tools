from abc import ABCMeta, abstractmethod
import dataclasses
import functools as ft
import itertools as it
import typing as tp

import libcst as cst


class FieldRemover(cst.CSTTransformer):
    @abstractmethod
    def skip_field(self, field: dataclasses.Field) -> bool: pass

    def on_leave(self,
            original_node: cst.CSTNode,
            updated_node: cst.CSTNode
            ) -> tp.Union[cst.CSTNode, cst.RemovalSentinel]:
        saved_fields = {}
        for field in dataclasses.fields(updated_node):
            if self.skip_field(field):
                continue

            n = field.name
            saved_fields[n] = getattr(updated_node, n)

        final_node = type(updated_node)(**saved_fields)
        return super().on_leave(original_node, final_node)


_WHITE_SPACE_TYPES: tp.Set[tp.Type[cst.CSTNode]] = frozenset((
    cst.Comment,
    cst.EmptyLine,
    cst.Newline,
    cst.ParenthesizedWhitespace,
    cst.SimpleWhitespace,
    cst.TrailingWhitespace,
    cst.BaseParenthesizableWhitespace,
))


_WHITE_SPACE_SEQUENCE_TYPES: tp.Set[tp.Type] = frozenset(
    tp.Sequence[t] for t in _WHITE_SPACE_TYPES
)


class WhiteSpaceNormalizer(FieldRemover):
    def skip_field(self, field: dataclasses.Field) -> bool:
        t = field.type
        return t in _WHITE_SPACE_TYPES or t in _WHITE_SPACE_SEQUENCE_TYPES


_PAREN_NAMES = ('lpar', 'rpar')


class StripParens(FieldRemover):
    def skip_field(self, field: dataclasses.Field) -> bool:
        return field.name in _PAREN_NAMES

def _normalize(node: cst.CSTNode):
    node = node.visit(StripParens())
    node = node.visit(WhiteSpaceNormalizer())
    node.validate_types_deep()
    return node


@ft.lru_cache(maxsize=2048)
def _deep_hash(node: cst.CSTNode):
    h = hash(type(node))
    try:
        h += hash(node.evaluated_value)
    except:
        pass

    for i,c in enumerate(node.children):
        h += (1+i)*_deep_hash(c)

    return h


class DeepNode(tp.Generic[cst.CSTNodeT], tp.Hashable):
    # Note because of:
    #  https://github.com/Instagram/LibCST/issues/341
    # the normalized node may not be equivelent to original node
    # as parens are removed from the normalized node
    original_node: cst.CSTNode
    normal_node: cst.CSTNode
    _hash: int

    def __init__(self, node: cst.CSTNode):
        self.original_node = node
        self.normal_node = norm = _normalize(node)
        self._hash = _deep_hash(norm)

    def __eq__(self, other: 'DeepNode') -> bool:
        if isinstance(other, DeepNode):
            return self.normal_node.deep_equals(other.normal_node)
        else:
            return NotImplemented


    def __ne__(self, other: 'DeepNode') -> bool:
        if isinstance(other, DeepNode):
            return not self.normal_node.deep_equals(other.normal_node)
        else:
            return NotImplemented

    def __hash__(self) -> int:
        return self._hash

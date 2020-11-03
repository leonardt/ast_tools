import dataclasses
import functools as ft
import typing as tp

import libcst as cst

_STRIPPED_ATTRS: tp.AbstractSet[str] =  frozenset({
        'header',
        'footer',
        'leading_lines',
        'lines_after_decorators',
        'lpar',
        'rpar',
})

_WHITE_SPACE_ATTR: str = 'whitespace'

class _Normalizer(cst.CSTTransformer):
    in_whitespace: bool

    def __init__(self):
        self.in_whitespace = False

    def on_visit(self, node: cst.CSTNode) -> tp.Optional[bool]:
        if isinstance(node, (
                cst.Comment,
                cst.EmptyLine,
                cst.Newline,
                cst.ParenthesizedWhitespace,
                cst.SimpleWhitespace,
                cst.TrailingWhitespace,
                cst.BaseParenthesizableWhitespace,
                )):
            self.in_whitespace = True
            return False
        else:
            assert not self.in_whitespace
            return super().on_visit(node)

    def on_leave(self,
            original_node: cst.CSTNode,
            updated_node: cst.CSTNode
            ) -> tp.Union[cst.CSTNode, cst.RemovalSentinel]:
        if self.in_whitespace:
            self.in_whitespace = False
            return super().on_leave(original_node, updated_node)

        saved_fields = {}
        for field in dataclasses.fields(updated_node):
            n = field.name
            # Hack to find whitespace fields
            if (n not in _STRIPPED_ATTRS
                and _WHITE_SPACE_ATTR not in n):
                saved_fields[n] = getattr(updated_node, n)

        final_node = type(updated_node)(**saved_fields)
        return super().on_leave(original_node, final_node)


def _normalize(node: cst.CSTNode):
    node = node.visit(_Normalizer())
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

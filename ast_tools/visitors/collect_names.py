"""
Defines a visitor that collects all names contained in an AST
"""

import collections.abc
import typing as tp

import libcst as cst
from libcst.metadata import ExpressionContext, ExpressionContextProvider

_OptContext = tp.Optional[ExpressionContext]

class NameCollector(cst.CSTVisitor):
    """
    Collect all instances of `Name` in a CST.
    """
    METADATA_DEPENDENCIES = (ExpressionContextProvider,)

    def __init__(self, ctx: tp.Union[tp.Sequence[_OptContext], _OptContext] = ()):
        """
        Set `ctx` to `STORE` or `LOAD` or `DEL` to  filter names.
        `ctx=None` will filter for names which are not names in the AST
        (e.g. attrs).
        """
        super().__init__()
        self.names = set()
        if ctx == ():
            ctx = frozenset((
                ExpressionContext.LOAD,
                ExpressionContext.STORE,
                ExpressionContext.DEL,))
        elif isinstance(ctx, collections.abc.Iterable):
            ctx = frozenset(ctx)
        else:
            ctx = frozenset((ctx,))
        self.ctx = ctx

    def visit_Name(self, node: cst.Name):
        ctx = self.get_metadata(ExpressionContextProvider, node)
        if ctx in self.ctx:
            self.names.add(node.value)


def collect_names(tree, ctx=()):
    """
    Convenience wrapper for NameCollector
    """
    visitor = NameCollector(ctx)
    wrapper = cst.MetadataWrapper(tree, unsafe_skip_copy=True)
    wrapper.visit(visitor)
    return visitor.names

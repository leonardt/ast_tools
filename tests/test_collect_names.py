"""
Test collecting instances of `ast.Name`
"""
import ast
from ast_tools import get_ast, collect_names


def test_collect_names_basic():
    """
    Test collecting names from a simple function including the `ctx` feature
    """
    def foo(bar, baz):  # pylint: disable=blacklisted-name
        buzz = bar + baz
        return buzz

    foo_ast = get_ast(foo)
    assert collect_names(foo_ast) == {"bar", "baz", "buzz"}
    assert collect_names(foo_ast, ctx=ast.Load) == {"bar", "baz", "buzz"}
    assert collect_names(foo_ast, ctx=ast.Store) == {"buzz"}

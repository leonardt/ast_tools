"""
Test visitors
"""
import libcst as cst

import pytest

from ast_tools.visitors import collect_names
from ast_tools.visitors import collect_targets
from ast_tools.visitors import used_names


def test_collect_targets():
    tree = cst.parse_module('''
x = [0, 1]
x[0] = 1
x.attr = 2
''')
    x = cst.Name(value='x')
    x0 = cst.Subscript(
            value=x,
            slice=[
                cst.SubscriptElement(
                    slice=cst.Index(value=cst.Integer('0'))
                )
            ],
    )
    xa = cst.Attribute(
            value=x,
            attr=cst.Name('attr'),
    )

    golds = x,x0,xa

    targets = collect_targets(tree)
    assert all(t.deep_equals(g) for t,g in zip(targets, golds))


def test_used_names():
    tree =  cst.parse_module('''
x = 1
def foo():
    def g(): pass

class A:
    def __init__(self): pass

    class B: pass

x.f = 7

async def h(): pass
''')
    assert used_names(tree) == {'x', 'foo', 'A', 'h'}
    assert used_names(tree.body[1].body) == {'g'}

# Currently broken requires new release of LibCSt
def test_collect_names():
    """
    Test collecting names from a simple function including the `ctx` feature
    """
    s = '''
def foo(bar, baz):  # pylint: disable=blacklisted-name
    buzz = bar + baz
    name_error
    del bar
    return buzz
'''

    foo_ast = cst.parse_module(s)
    assert collect_names(foo_ast, ctx=cst.metadata.ExpressionContext.STORE) == {"foo", "bar", "baz", "buzz"}
    assert collect_names(foo_ast, ctx=cst.metadata.ExpressionContext.LOAD) == {"bar", "baz", "buzz", "name_error"}
    assert collect_names(foo_ast, ctx=cst.metadata.ExpressionContext.DEL) == {"bar"}
    assert collect_names(foo_ast) == {"foo", "bar", "baz", "buzz", "name_error"}


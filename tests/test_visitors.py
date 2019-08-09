"""
Test collecting instances of `ast.Name`
"""
import ast
from ast_tools.visitors import collect_names
from ast_tools.visitors import UsedNames

def test_collect_names_basic():
    """
    Test collecting names from a simple function including the `ctx` feature
    """
    s = '''
def foo(bar, baz):  # pylint: disable=blacklisted-name
    buzz = bar + baz
    return buzz
'''

    foo_ast = ast.parse(s)
    assert collect_names(foo_ast) == {"bar", "baz", "buzz"}
    assert collect_names(foo_ast, ctx=ast.Load) == {"bar", "baz", "buzz"}
    assert collect_names(foo_ast, ctx=ast.Store) == {"buzz"}


def test_used_names():
    tree =  ast.parse('''
x = 1
def foo():
    def g():
        pass
class A:
    def __init__(self): pass

    class B: pass

async def h(): pass
''')
    visitor = UsedNames()
    visitor.visit(tree)
    assert visitor.names == {'x', 'foo', 'A', 'h'}

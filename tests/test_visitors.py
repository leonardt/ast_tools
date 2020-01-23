"""
Test visitors
"""
import ast
from ast_tools.visitors import collect_names
from ast_tools.visitors import collect_targets
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


def test_collect_targets():
    tree = ast.parse('''
x = [0, 1]
x[0] = 1
x.attr = 2
''')
    targets = collect_targets(tree)

    # All of this because of nodes aren't comparable.
    def _check_name(node, ctx=ast.Store):
        assert isinstance(node, ast.Name)
        assert node.id == 'x'
        assert isinstance(node.ctx, ctx)

    def _check_subs(node):
        assert isinstance(node, ast.Subscript)
        _check_name(node.value, ast.Load)
        assert isinstance(node.slice, ast.Index)
        assert isinstance(node.slice.value, ast.Num)
        assert node.slice.value.n == 0
        assert isinstance(node.ctx, ast.Store)

    def _check_attr(node):
        assert isinstance(node, ast.Attribute)
        _check_name(node.value, ast.Load)
        assert node.attr == 'attr'
        assert isinstance(node.ctx, ast.Store)

    for t in targets:
        if isinstance(t, ast.Name):
            _check_name(t)
        elif isinstance(t, ast.Subscript):
            _check_subs(t)
        else:
            _check_attr(t)

    targets = collect_targets(tree, ast.Name)
    for t in targets:
        _check_name(t)

    targets = collect_targets(tree, ast.Subscript)
    for t in targets:
        _check_subs(t)

    targets = collect_targets(tree, ast.Attribute)
    for t in targets:
        _check_attr(t)

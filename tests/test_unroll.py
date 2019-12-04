import inspect
import ast
import astor
from ast_tools.transformers.loop_unroller import unroll_for_loops
from ast_tools.passes import begin_rewrite, end_rewrite, loop_unroll


def test_basic_unroll():
    tree = ast.parse("""
def foo():
    for i in range(8, unroll=True):
        print(i)
""")
    assert astor.to_source(unroll_for_loops(tree, {})) == """\
def foo():
    print(0)
    print(1)
    print(2)
    print(3)
    print(4)
    print(5)
    print(6)
    print(7)
"""


def test_basic_inside_if():
    tree = ast.parse("""
def foo(x):
    if x:
        for i in range(8, unroll=True):
            print(i)
        return x + 1 if x % 2 else x
    else:
        print(x)
        for j in range(2, unroll=True):
            print(j - 1)
""")
    assert astor.to_source(unroll_for_loops(tree, {})) == """\
def foo(x):
    if x:
        print(0)
        print(1)
        print(2)
        print(3)
        print(4)
        print(5)
        print(6)
        print(7)
        return x + 1 if x % 2 else x
    else:
        print(x)
        print(0 - 1)
        print(1 - 1)
"""


def test_basic_inside_while():
    tree = ast.parse("""
def foo(x):
    while True:
        for i in range(8, unroll=True):
            print(i)
""")
    assert astor.to_source(unroll_for_loops(tree, {})) == """\
def foo(x):
    while True:
        print(0)
        print(1)
        print(2)
        print(3)
        print(4)
        print(5)
        print(6)
        print(7)
"""


def test_basic_env():
    tree = ast.parse("""
def foo(x):
    for i in range(j, unroll=True):
        print(i)
""")
    assert astor.to_source(unroll_for_loops(tree, {"j": 2})) == """\
def foo(x):
    print(0)
    print(1)
"""


def test_pass_basic():
    @end_rewrite()
    @loop_unroll()
    @begin_rewrite()
    def foo():
        for i in range(8, unroll=True):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    print(0)
    print(1)
    print(2)
    print(3)
    print(4)
    print(5)
    print(6)
    print(7)
"""


def test_pass_env():
    j = 3
    @end_rewrite()
    @loop_unroll()
    @begin_rewrite()
    def foo():
        for i in range(j, unroll=True):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    print(0)
    print(1)
    print(2)
"""

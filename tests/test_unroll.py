import inspect
import ast
import astor
from ast_tools.transformers.loop_unroller import unroll_for_loops
from ast_tools.passes import begin_rewrite, end_rewrite, loop_unroll
import ast_tools


def test_basic_unroll():
    tree = ast.parse("""
def foo():
    for i in ast_tools.macros.unroll(range(8)):
        print(i)
""")
    assert astor.to_source(unroll_for_loops(tree, globals())) == """\
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
        for i in ast_tools.macros.unroll(range(8)):
            print(i)
        return x + 1 if x % 2 else x
    else:
        print(x)
        for j in ast_tools.macros.unroll(range(2)):
            print(j - 1)
""")
    assert astor.to_source(unroll_for_loops(tree, globals())) == """\
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
        for i in ast_tools.macros.unroll(range(8)):
            print(i)
""")
    assert astor.to_source(unroll_for_loops(tree, globals())) == """\
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
    for i in ast_tools.macros.unroll(range(j)):
        print(i)
""")
    env = dict(globals(), **{"j": 2})
    assert astor.to_source(unroll_for_loops(tree, env)) == """\
def foo(x):
    print(0)
    print(1)
"""


def test_pass_basic():
    @end_rewrite()
    @loop_unroll()
    @begin_rewrite()
    def foo():
        for i in ast_tools.macros.unroll(range(8)):
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
        for i in ast_tools.macros.unroll(range(j)):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    print(0)
    print(1)
    print(2)
"""


def test_pass_no_unroll():
    j = 3
    @end_rewrite()
    @loop_unroll()
    @begin_rewrite()
    def foo():
        for i in range(j):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    for i in range(j):
        print(i)
"""


def test_pass_no_unroll_nested():
    j = 3
    @end_rewrite()
    @loop_unroll()
    @begin_rewrite()
    def foo():
        for i in range(j):
            for k in ast_tools.macros.unroll(range(3)):
                print(i * k)
    assert inspect.getsource(foo) == """\
def foo():
    for i in range(j):
        print(i * 0)
        print(i * 1)
        print(i * 2)
"""


def test_pass_no_rewrite_range():
    j = 3

    def foo():
        count = 0
        for i in range(j):
            for k in ast_tools.macros.unroll(range(3)):
                count += 1
        return count
    assert foo() == 3 * 3

import inspect

import pytest

import libcst as cst

import ast_tools
from ast_tools.transformers.loop_unroller import unroll_for_loops
from ast_tools.passes import apply_passes, loop_unroll
from ast_tools.cst_utils import to_module



def test_basic_unroll():
    src = """\
def foo():
    for i in ast_tools.macros.unroll(range(8)):
        print(i)
"""
    unrolled_src = """\
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
    tree = cst.parse_module(src)
    unrolled_tree = unroll_for_loops(tree, globals())
    assert to_module(unrolled_tree).code == unrolled_src


def test_basic_inside_if():
    src = """\
def foo(x):
    if x:
        for i in ast_tools.macros.unroll(range(8)):
            print(i)
        return x + 1 if x % 2 else x
    else:
        print(x)
        for j in ast_tools.macros.unroll(range(2)):
            print(j - 1)
"""
    unrolled_src = """\
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
    tree = cst.parse_module(src)
    unrolled_tree = unroll_for_loops(tree, globals())
    assert to_module(unrolled_tree).code == unrolled_src


def test_basic_inside_while():
    src = """\
def foo(x):
    while True:
        for i in ast_tools.macros.unroll(range(8)):
            print(i)
"""
    unrolled_src = """\
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
    tree = cst.parse_module(src)
    unrolled_tree = unroll_for_loops(tree, globals())
    assert to_module(unrolled_tree).code == unrolled_src


def test_basic_env():
    src = """\
def foo(x):
    for i in ast_tools.macros.unroll(range(j)):
        print(i)
"""
    unrolled_src = """\
def foo(x):
    print(0)
    print(1)
"""
    env = dict(globals(), **{"j": 2})
    tree = cst.parse_module(src)
    unrolled_tree = unroll_for_loops(tree, env)
    assert to_module(unrolled_tree).code == unrolled_src


def test_pass_basic():
    @apply_passes([loop_unroll()])
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
    @apply_passes([loop_unroll()])
    def foo():
        for i in ast_tools.macros.unroll(range(j)):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    print(0)
    print(1)
    print(2)
"""


def test_pass_nested():
    @apply_passes([loop_unroll()])
    def foo():
        for i in ast_tools.macros.unroll(range(2)):
            for j in ast_tools.macros.unroll(range(3)):
                print(i + j)
    assert inspect.getsource(foo) == """\
def foo():
    print(0 + 0)
    print(0 + 1)
    print(0 + 2)
    print(1 + 0)
    print(1 + 1)
    print(1 + 2)
"""


def test_pass_no_unroll():
    j = 3
    @apply_passes([loop_unroll()])
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
    @apply_passes([loop_unroll()])
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


def test_bad_iter():
    with pytest.raises(Exception):
        @apply_passes([loop_unroll()])
        def foo():
            count = 0
            for k in ast_tools.macros.unroll([object(), object()]):
                count += 1
            return count


def test_list_of_ints():
    j = [1, 2, 3]
    @apply_passes([loop_unroll()])
    def foo():
        for i in ast_tools.macros.unroll(j):
            print(i)
    assert inspect.getsource(foo) == """\
def foo():
    print(1)
    print(2)
    print(3)
"""

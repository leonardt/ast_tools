import inspect

import pytest

from ast_tools.macros import inline
from ast_tools.passes import apply_passes, if_inline


@pytest.mark.parametrize('cond', [False, True])
def test_basic(cond):
    def basic():
        if inline(cond):
            return 0
        else:
            return 1

    inlined = apply_passes([if_inline()])(basic)
    inlined_src = inspect.getsource(inlined)
    print(inlined_src)
    assert inlined_src == f'''\
def basic():
    return {0 if cond else 1}
'''
    assert basic() == inlined()

@pytest.mark.parametrize('cond_0', [False, True])
@pytest.mark.parametrize('cond_1', [False, True])
def test_nested(cond_0, cond_1):
    def nested():
        if inline(cond_0):
            if inline(cond_1):
                return 3
            else:
                return 2
        else:
            if inline(cond_1):
                return 1
            else:
                return 0

    inlined = apply_passes([if_inline()])(nested)
    assert inspect.getsource(inlined) == f'''\
def nested():
    return {nested()}
'''
    assert nested() == inlined()

@pytest.mark.parametrize('cond_0', [False, True])
@pytest.mark.parametrize('cond_1', [False, True])
def test_inner_inline(cond_0, cond_1):
    def nested(cond):
        if cond:
            if inline(cond_1):
                return 3
            else:
                return 2
        else:
            if inline(cond_1):
                return 1
            else:
                return 0

    inlined = apply_passes([if_inline()])(nested)
    assert inspect.getsource(inlined) == f'''\
def nested(cond):
    if cond:
        return {3 if cond_1 else 2}
    else:
        return {1 if cond_1 else 0}
'''
    assert nested(cond_0) == inlined(cond_0)

@pytest.mark.parametrize('cond_0', [False, True])
@pytest.mark.parametrize('cond_1', [False, True])
def test_outer_inline(cond_0, cond_1):
    def nested(cond):
        if inline(cond_0):
            if cond:
                return 3
            else:
                return 2
        else:
            if cond:
                return 1
            else:
                return 0

    inlined = apply_passes([if_inline()])(nested)
    assert inspect.getsource(inlined) == f'''\
def nested(cond):
    if cond:
        return {3 if cond_0 else 1}
    else:
        return {2 if cond_0 else 0}
'''
    assert nested(cond_1) == inlined(cond_1)


def test_readme_example():
    y = True
    @apply_passes([if_inline()])
    def foo(x):
        if inline(y):
            return x + 1
        else:
            return x - 1
    assert inspect.getsource(foo) == f"""\
def foo(x):
    return x + 1
"""

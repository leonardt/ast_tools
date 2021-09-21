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


@pytest.mark.parametrize('cond', [False, True])
def test_if_no_else(cond):
    def if_no_else():
        x = 0
        if inline(cond):
            x = 1
        return x

    if cond:
        gold_src = '''\
def if_no_else():
    x = 0
    x = 1
    return x
'''
    else:
        gold_src = '''\
def if_no_else():
    x = 0
    return x
'''
    inlined = apply_passes([if_inline()])(if_no_else)
    assert inspect.getsource(inlined) == gold_src
    assert if_no_else() == inlined()


@pytest.mark.parametrize('cond_0', [False, True])
@pytest.mark.parametrize('cond_1', [False, True])
def test_if_elif(cond_0, cond_1):
    def if_elif():
        x = 0
        if inline(cond_0):
            x = 1
        elif inline(cond_1):
            x = 2
        return x

    gold_lines = ['def if_elif():', '{tab}x = 0']
    if cond_0:
        gold_lines.append('{tab}x = 1')
    elif cond_1:
        gold_lines.append('{tab}x = 2')

    gold_lines.append('{tab}return x\n')

    gold_src = '\n'.join(gold_lines).format(tab='    ')
    inlined = apply_passes([if_inline()])(if_elif)
    assert inspect.getsource(inlined) == gold_src
    assert if_elif() == inlined()


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

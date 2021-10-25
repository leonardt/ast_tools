from collections import namedtuple
import inspect
import random

import libcst as cst

import pytest

from ast_tools.common import exec_def_in_file
from ast_tools.passes.ssa import ssa
from ast_tools.passes import apply_passes, debug
from ast_tools.stack import SymbolTable



NTEST = 16

basic_template = '''\
def basic(x):
    if x:
        {} 0
    else:
        {} 2
    {}
'''

template_options = ['r =', 'return']

def _do_ssa(func, strict, **kwargs):
    for dec in (
            begin_rewrite(),
            debug(**kwargs),
            ssa(strict),
            debug(**kwargs),
            end_rewrite()):
        func = dec(func)
    return func


@pytest.mark.parametrize('strict', [True, False])
@pytest.mark.parametrize('a', template_options)
@pytest.mark.parametrize('b', template_options)
def test_basic_if(strict, a, b):
    if a == b == 'return':
        final = ''
    else:
        final = 'return r'

    src = basic_template.format(a, b, final)
    tree = cst.parse_statement(src)
    env = SymbolTable({}, {})
    basic = exec_def_in_file(tree, env)
    ssa_basic = apply_passes([ssa(strict)])(basic)

    for x in (False, True):
        assert basic(x) == ssa_basic(x)


nested_template = '''\
def nested(x, y):
    if x:
        if y:
            {} 0
        else:
            {} 1
    else:
        if y:
            {} 2
        else:
            {} 3
    {}
'''

@pytest.mark.parametrize('strict', [True, False])
@pytest.mark.parametrize('a', template_options)
@pytest.mark.parametrize('b', template_options)
@pytest.mark.parametrize('c', template_options)
@pytest.mark.parametrize('d', template_options)
def test_nested(strict, a, b, c, d):
    if a == b == c == d == 'return':
        final = ''
    else:
        final = 'return r'

    src = nested_template.format(a, b, c, d, final)
    tree = cst.parse_statement(src)
    env = SymbolTable({}, {})
    nested = exec_def_in_file(tree, env)
    ssa_nested = apply_passes([ssa(strict)])(nested)

    for x in (False, True):
        for y in (False, True):
            assert nested(x, y) == ssa_nested(x, y)

imbalanced_template = '''\
def imbalanced(x, y):
    {} -1
    if x:
        {} -2
        if y:
            {} 0
    else:
        {} 1
    return r
'''

init_template_options = ['r = ', '0']

@pytest.mark.parametrize('strict', [True, False])
@pytest.mark.parametrize('a', init_template_options)
@pytest.mark.parametrize('b', init_template_options)
@pytest.mark.parametrize('c', template_options)
@pytest.mark.parametrize('d', template_options)
def test_imbalanced(strict, a, b, c, d):
    src = imbalanced_template.format(a, b, c, d)
    tree = cst.parse_statement(src)
    env = SymbolTable({}, {})
    imbalanced = exec_def_in_file(tree, env)
    can_name_error = False
    for x in (False, True):
        for y in (False, True):
            try:
                imbalanced(x, y)
            except NameError:
                can_name_error = True
                break

    if can_name_error and strict:
        with pytest.raises(SyntaxError):
            ssa_imbalanced = apply_passes([ssa(strict)])(imbalanced)
    else:
        ssa_imbalanced = apply_passes([ssa(strict)])(imbalanced)
        for x in (False, True):
            for y in (False, True):
                try:
                    assert imbalanced(x, y) == ssa_imbalanced(x, y)
                except NameError:
                    assert can_name_error



def test_reassign_arg():
    def bar(x):
        return x

    @apply_passes([ssa()], metadata_attr='metadata')
    def foo(a, b):
        if b:
            a = len(a)
        return a
    assert inspect.getsource(foo) == '''\
def foo(a, b):
    _cond_0 = b
    a_0 = len(a)
    a_1 = a_0 if _cond_0 else a
    __0_return_0 = a_1
    return __0_return_0
'''
    symbol_tables = foo.metadata['SYMBOL-TABLE']
    assert len(symbol_tables) == 1
    assert symbol_tables[0][0] == ssa
    symbol_table = symbol_tables[0][1]
    assert symbol_table == {
        2: {
            'a': 'a',
            'b': 'b',
        },
        3: {
            'a': 'a',
            'b': 'b',
        },
        4: {
            'a': 'a_0',
            'b': 'b',
        },
        5: {
            'a': 'a_1',
            'b': 'b',
        },
    }


def test_double_nested_function_call():
    def bar(x):
        return x

    def baz(x):
        return x + 1

    @apply_passes([ssa()], metadata_attr='metadata') # 1
    def foo(a, b, c):   # 2
        if b:           # 3
            a = bar(a)  # 4
        else:           # 5
            a = bar(a)  # 6
        if c:           # 7
            b = bar(b)  # 8
        else:           # 9
            b = bar(b)  # 10
        return a, b     # 11
    assert inspect.getsource(foo) == '''\
def foo(a, b, c):   # 2
    _cond_0 = b
    a_0 = bar(a)  # 4
    a_1 = bar(a)  # 6
    a_2 = a_0 if _cond_0 else a_1
    _cond_1 = c
    b_0 = bar(b)  # 8
    b_1 = bar(b)  # 10
    b_2 = b_0 if _cond_1 else b_1
    __0_return_0 = a_2, b_2     # 11
    return __0_return_0
'''

    symbol_tables = foo.metadata['SYMBOL-TABLE']
    assert len(symbol_tables) == 1
    assert symbol_tables[0][0] == ssa
    symbol_table = symbol_tables[0][1]
    gold_table = {i: {
        'a': 'a' if i < 4 else 'a_0' if i <  6 else 'a_1' if i <  7 else 'a_2',
        'b': 'b' if i < 8 else 'b_0' if i < 10 else 'b_1' if i < 11 else 'b_2',
        'c': 'c',
        } for i in range(2, 12)}
    assert symbol_table == gold_table

class Thing:
    def __init__(self, x=None):
        self.x = x

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.x == other.x
        else:
            return self.x == other

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return f'Thing({self.x})'

@pytest.mark.parametrize('strict', [True, False])
def test_attrs_basic(strict):
    def f1(t, cond):
        old = t.x
        if cond:
            t.x = 1
        else:
            t.x = 0
        return old

    f2  = apply_passes([ssa(strict)])(f1)

    t1 = Thing()
    t2 = Thing()

    assert t1 == t2 == None
    f1(t1, True)
    assert t1 != t2
    f2(t2, True)
    assert t1 == t2 == 1
    f1(t1, False)
    assert t1 != t2
    f2(t2, False)
    assert t1 == t2 == 0


@pytest.mark.parametrize('strict', [True, False])
def test_attrs_returns(strict):
    def f1(t, cond1, cond2):
        if cond1:
            t.x = 1
            if cond2:
                return 0
        else:
            t.x = 0
            if cond2:
                return 1
        return -1

    f2  = apply_passes([ssa(strict)])(f1)

    t1 = Thing()
    t2 = Thing()
    assert t1 == t2

    for _ in range(NTEST):
        c1 = random.randint(0, 1)
        c2 = random.randint(0, 1)
        o1 = f1(t1, c1, c2)
        o2 = f2(t2, c1, c2)
        assert o1 == o2
        assert t1 == t2


@pytest.mark.parametrize('strict', [True, False])
def test_attrs_class(strict):
    class Counter1:
        def __init__(self, init, max):
            self.cnt = init
            self.max = max

        def __call__(self, en):
            if en and self.cnt < self.max - 1:
                self.cnt = self.cnt + 1
            elif en:
                self.cnt = 0

    class Counter2:
        __init__ = Counter1.__init__
        __call__ = apply_passes([ssa(strict)])(Counter1.__call__)

    c1 = Counter1(3, 5)
    c2 = Counter2(3, 5)

    assert c1.cnt == c2.cnt

    for _ in range(NTEST):
        e = random.randint(0, 1)
        o1 = c1(e)
        o2 = c2(e)
        assert o1 == o2
        assert c1.cnt == c2.cnt

@pytest.mark.parametrize('strict', [True, False])
def test_attrs_class_methods(strict):
    class Counter1:
        def __init__(self, init, max):
            self.cnt = init
            self.max = max

        def __call__(self, en):
            if en and self.cnt < self.max - 1:
                self.cnt = self.cnt + self.get_step(self.cnt)
            elif en:
                self.cnt = 0

        def get_step(self, cnt):
            return (cnt % 2) + 1

    class Counter2:
        __init__ = Counter1.__init__
        __call__ = apply_passes([ssa(strict)])(Counter1.__call__)
        get_step = Counter1.get_step

    c1 = Counter1(3, 5)
    c2 = Counter2(3, 5)

    assert c1.cnt == c2.cnt

    for _ in range(NTEST):
        e = random.randint(0, 1)
        o1 = c1(e)
        o2 = c2(e)
        assert o1 == o2
        assert c1.cnt == c2.cnt


def test_nstrict():
    # This function would confuse strict ssa in so many ways
    def f1(cond):
        if cond:
            if cond:
                return 0
        elif not cond:
            z = 1

        if not cond:
            x = z
            return x

    f2 = apply_passes([ssa(False)])(f1)
    assert inspect.getsource(f2) == '''\
def f1(cond):
    _cond_2 = cond
    _cond_0 = cond
    __0_return_0 = 0
    _cond_1 = not cond
    z_0 = 1
    _cond_3 = not cond
    x_0 = z_0
    __0_return_1 = x_0
    return __0_return_0 if _cond_2 and _cond_0 else __0_return_1
'''
    for cond in [True, False]:
        assert f1(cond) == f2(cond)


def test_attr():
    bar = namedtuple('bar', ['x', 'y'])

    def f1(x, y):
        z = bar(1, 0)
        if x:
            a = z
        else:
            a = y
        a.x = 3
        return a

    f2 = apply_passes([ssa(False)])(f1)
    assert inspect.getsource(f2) == '''\
def f1(x, y):
    _attr_a_x_0 = a.x
    z_0 = bar(1, 0)
    _cond_0 = x
    a_0 = z_0
    a_1 = y
    a_2 = a_0 if _cond_0 else a_1
    _attr_a_x_1 = 3
    __0_final_a_x_0 = _attr_a_x_1; __0_return_0 = a_2
    a_2.x = __0_final_a_x_0
    return __0_return_0
'''


def test_call():
    def f1(x):
        x = 2
        return g(x=x)

    f2 = apply_passes([ssa(False)])(f1)
    assert inspect.getsource(f2) == '''\
def f1(x):
    x_0 = 2
    __0_return_0 = g(x=x_0)
    return __0_return_0
'''


def ident(x): return x

sig_template = '''\
def f(x{}, y{}) -> ({}, {}):
    return x, y
'''


template_options = ['', 'int', 'ident(int)', 'ident(x=int)']

@pytest.mark.parametrize('strict', [True, False])
@pytest.mark.parametrize('x', template_options)
@pytest.mark.parametrize('y', template_options)
def test_call_in_annotations(strict, x, y):
    r_x = x if x else 'int'
    r_y = y if y else 'int'
    x = f': {x}' if x else x
    y = f': {y}' if y else y
    src = sig_template.format(x, y, r_x, r_y)
    tree = cst.parse_statement(src)
    env = SymbolTable(locals(), globals())
    f1 = exec_def_in_file(tree, env)
    f2 = apply_passes([ssa(strict)])(f1)


@pytest.mark.parametrize('strict', [True, False])
def test_issue_79(strict):
    class Wrapper:
        def __init__(self, val):
            self.val = val
        def apply(self, f):
            return f(self.val)

    def f1(x):
        return x.apply(lambda x: x+1)

    f2 = apply_passes([ssa(strict)])(f1)

    for _ in range(8):
        x = Wrapper(random.randint(0, 1<<10))
        assert f1(x) == f2(x)

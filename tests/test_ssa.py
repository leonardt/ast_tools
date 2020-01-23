import ast
import inspect
import random

import pytest

from ast_tools.common import exec_def_in_file
from ast_tools.passes import begin_rewrite, end_rewrite, ssa, debug
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
    tree = ast.parse(src).body[0]
    env = SymbolTable({}, {})
    basic = exec_def_in_file(tree, env)
    ssa_basic = _do_ssa(basic, strict, dump_src=True)

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
    tree = ast.parse(src).body[0]
    env = SymbolTable({}, {})
    nested = exec_def_in_file(tree, env)
    ssa_nested = _do_ssa(nested, strict, dump_src=True)

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
    tree = ast.parse(src).body[0]
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
            imbalanced_ssa = _do_ssa(imbalanced, strict, dump_src=True)
    elif not can_name_error:
        imbalanced_ssa = _do_ssa(imbalanced, strict, dump_src=True)
        for x in (False, True):
            for y in (False, True):
                assert imbalanced(x, y) == imbalanced_ssa(x, y)


def test_reassign_arg():
    def bar(x):
        return x

    @end_rewrite()
    @ssa()
    @begin_rewrite()
    def foo(a, b):
        if b:
            a = len(a)
        return a
    assert inspect.getsource(foo) == '''\
def foo(a, b):
    a0 = len(a)
    a1 = a0 if b else a
    __return_value0 = a1
    return __return_value0
'''


def test_double_nested_function_call():
    def bar(x):
        return x

    def baz(x):
        return x + 1

    @end_rewrite()
    @ssa()
    @begin_rewrite()
    def foo(a, b, c):
        if b:
            a = bar(a)
        else:
            a = bar(a)
        if c:
            b = bar(b)
        else:
            b = bar(b)
        return a, b
    print(inspect.getsource(foo))
    assert inspect.getsource(foo) == '''\
def foo(a, b, c):
    a0 = bar(a)
    a1 = bar(a)
    a2 = a0 if b else a1
    b0 = bar(b)
    b1 = bar(b)
    b2 = b0 if c else b1
    __return_value0 = a2, b2
    return __return_value0
'''

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

    f2  = _do_ssa(f1, strict, dump_ast=True, dump_src=True)

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

    f2  = _do_ssa(f1, strict, dump_src=True)

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
        __call__ = _do_ssa(Counter1.__call__, strict, dump_ast=True, dump_src=True)

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
        __call__ = _do_ssa(Counter1.__call__, strict, dump_ast=True, dump_src=True)
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

    f2 = _do_ssa(f1, False, dump_src=True)
    assert inspect.getsource(f2) == '''\
def f1(cond):
    __return_value0 = 0
    z0 = 1
    x0 = z0
    __return_value1 = x0
    return __return_value0 if cond and cond else __return_value1
'''
    for cond in [True, False]:
        assert f1(cond) == f2(cond)

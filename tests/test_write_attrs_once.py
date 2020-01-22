import ast
import inspect
import random

import pytest

from ast_tools.common import exec_def_in_file
from ast_tools.passes import begin_rewrite, end_rewrite, write_attrs_once, debug
from ast_tools.stack import SymbolTable

NTEST = 32

def _do_wao(func, **kwargs):
    for dec in (
            begin_rewrite(),
            debug(**kwargs),
            write_attrs_once(),
            debug(**kwargs),
            end_rewrite()):
        func = dec(func)
    return func

class Thing:
    def __init__(self):
        self.x = None

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self.x == other.x
        else:
            return self.x == other

    def __ne__(self, other):
        return not (self == other)

def test_basic():
    def f1(t, cond):
        if cond:
            t.x = 1
        else:
            t.x = 0

    f2  = _do_wao(f1, dump_src=True)

    assert inspect.getsource(f2) == '''\
def f1(t, cond):
    t_x = t.x
    if cond:
        t_x = 1
    else:
        t_x = 0
    t.x = t_x
'''

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


def test_returns():
    def f1(t, cond1, cond2):
        if cond1:
            t.x = 1
            if cond2:
                return 0
        else:
            t.x = 0
            if cond2:
                return 1

    f2  = _do_wao(f1, dump_src=True)

    assert inspect.getsource(f2) == '''\
def f1(t, cond1, cond2):
    t_x = t.x
    if cond1:
        t_x = 1
        if cond2:
            t.x = t_x
            return 0
    else:
        t_x = 0
        if cond2:
            t.x = t_x
            return 1
    t.x = t_x
'''

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


def test_class():
    class Counter1:
        def __init__(self, init, max):
            self.cnt = init
            self.max = max

        def __call__(self, en):
            if en and self.cnt < self.max - 1:
                self.cnt = self.cnt + 1
                return 1
            elif en:
                self.cnt = 0
                return -1
            return 0

    class Counter2:
        __init__ = Counter1.__init__
        __call__ = _do_wao(Counter1.__call__)

    assert inspect.getsource(Counter2.__call__) == '''\
def __call__(self, en):
    self_cnt = self.cnt
    if en and self_cnt < self.max - 1:
        self_cnt = self_cnt + 1
        self.cnt = self_cnt
        return 1
    elif en:
        self_cnt = 0
        self.cnt = self_cnt
        return -1
    self.cnt = self_cnt
    return 0
'''

    c1 = Counter1(3, 5)
    c2 = Counter2(3, 5)

    assert c1.cnt == c2.cnt

    for _ in range(NTEST):
        e = random.randint(0, 1)
        o1 = c1(e)
        o2 = c2(e)
        assert o1 == o2
        assert c1.cnt == c2.cnt

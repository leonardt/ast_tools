import ast
import inspect

import pytest


from ast_tools.passes import apply_passes, bool_to_bit

def test_and():
    @apply_passes([bool_to_bit()])
    def and_f(x, y):
        return x and y

    assert inspect.getsource(and_f) == '''\
def and_f(x, y):
    return x & y
'''

def test_or():
    @apply_passes([bool_to_bit()])
    def or_f(x, y):
        return x or y

    assert inspect.getsource(or_f) == '''\
def or_f(x, y):
    return x | y
'''

def test_not():
    @apply_passes([bool_to_bit()])
    def not_f(x):
        return not x

    assert inspect.getsource(not_f) == '''\
def not_f(x):
    return ~x
'''

def test_xor():
    @apply_passes([bool_to_bit()])
    def xor(x, y):
        return x and not y or not x and y

    assert inspect.getsource(xor) == '''\
def xor(x, y):
    return x & ~y | ~x & y
'''


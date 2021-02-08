import ast
import inspect

import pytest

from ast_tools.passes import apply_ast_passes, cse, ssa, debug

@pytest.mark.skip()
def test_basic():
    @apply_ast_passes([ssa(), cse()])
    def foo(a, b, c):
        x = a + b
        y = a + b + c
        z = a + b - c
        return x + y + z

    assert inspect.getsource(foo) == '''\
def foo(a, b, c):
    __common_expr0 = a + b
    x0 = __common_expr0
    y0 = __common_expr0 + c
    z0 = __common_expr0 - c
    __return_value0 = x0 + y0 + z0
    return __return_value0
'''


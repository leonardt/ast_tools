import ast
import inspect

import pytest

from ast_tools.passes import apply_passes, if_to_phi


def mux(select, t, f):
    return t if select else f


@pytest.mark.parametrize('phi_args, expected_name', [
    ([mux], '__phi'), # test passing function
    (['mux'], 'mux'), # test passing name
    ([mux, 'foo'], 'foo'), # test passing function and free name
    ([mux, 'mux'], 'mux0'), # test passing function and used name
    ])
def test_basic(phi_args, expected_name):
    def basic(s):
        return 0 if s else 1

    phi_basic = apply_passes([if_to_phi(*phi_args)])(basic)

    for s in (True, False):
        assert basic(s) == phi_basic(s)

    assert inspect.getsource(phi_basic) == f'''\
def basic(s):
    return {expected_name}(s, 0, 1)
'''


@pytest.mark.parametrize('phi_args, expected_name', [
    ([mux], '__phi'), # test passing function
    (['mux'], 'mux'), # test passing name
    ([mux, 'foo'], 'foo'), # test passing function and free name
    ([mux, 'mux'], 'mux0'), # test passing function and used name
    ])
def test_nested(phi_args, expected_name):
    def nested(s, t):
        return 0 if s else 1 if t else 2

    phi_nested = apply_passes([if_to_phi(*phi_args)])(nested)

    for s in (True, False):
        for t in (True, False):
            assert nested(s, t) == phi_nested(s, t)

    assert inspect.getsource(phi_nested) == f'''\
def nested(s, t):
    return {expected_name}(s, 0, {expected_name}(t, 1, 2))
'''

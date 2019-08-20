import ast

import pytest

from ast_tools.common import exec_def_in_file
from ast_tools.passes import begin_rewrite, end_rewrite, ssa
from ast_tools.stack import SymbolTable

basic_template = '''\
def basic(x):
    if x:
        {} 0
    else:
        {} 2
    {}
'''

template_options = ['r =', 'return']

@pytest.mark.parametrize("a", template_options)
@pytest.mark.parametrize("b", template_options)
def test_basic_if(a, b):
    if a == b == 'return':
        final = ''
    else:
        final = 'return r'

    src = basic_template.format(a, b, final)
    tree = ast.parse(src).body[0]
    env = SymbolTable({}, {})
    basic = exec_def_in_file(tree, env)
    ssa_basic = end_rewrite()(ssa()(begin_rewrite()(basic)))

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

@pytest.mark.parametrize("a", template_options)
@pytest.mark.parametrize("b", template_options)
@pytest.mark.parametrize("c", template_options)
@pytest.mark.parametrize("d", template_options)
def test_nested(a,b,c,d):
    if a == b == c == d == 'return':
        final = ''
    else:
        final = 'return r'

    src = nested_template.format(a, b, c, d, final)
    tree = ast.parse(src).body[0]
    env = SymbolTable({}, {})
    nested = exec_def_in_file(tree, env)
    ssa_nested = end_rewrite()(ssa()(begin_rewrite()(nested)))

    for x in (False, True):
        for y in (False, True):
            assert nested(x, y) == ssa_nested(x, y)

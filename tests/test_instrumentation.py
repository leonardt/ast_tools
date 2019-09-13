import pytest
import importlib
import sys

from ast_tools import instrumentation
from ast_tools.common import get_ast
from ast_tools import immutable_ast as iast

def _reset():
    del sys.modules['target']
    importlib.invalidate_caches()

import target as base_target
_reset()

@pytest.mark.parametrize("name", base_target.__ALL__)
def test_basic(name):
    instrumentation.activate(False)
    import target
    def_g = getattr(base_target, name)
    def_i = getattr(target, name)
    g_tree = get_ast(def_g)
    i_tree = instrumentation.INFO[def_i]['ast']
    assert 'env' not in instrumentation.INFO[def_i]
    if isinstance(i_tree, iast.ClassDef):
        # inspect doesn't get the decorator_list for classes
        i_tree = i_tree.replace(decorator_list=())
    assert i_tree == g_tree
    instrumentation.deactivate()
    _reset()

@pytest.mark.parametrize("name", base_target.__ALL__)
def test_env(name):
    instrumentation.activate(True)
    import target
    seen = {}
    def_ = getattr(target, name)
    assert set(target.__ALL__) <= instrumentation.INFO[def_]['env'][0].keys()
    instrumentation.deactivate()
    _reset()


def test_closure():
    instrumentation.activate(True)
    import target
    def_g = base_target.h()
    def_i = target.h()
    g_tree = get_ast(def_g)
    i_tree = instrumentation.INFO[def_i]['ast']
    assert i_tree == g_tree
    assert instrumentation.INFO[def_i]['env'][0]['local_var'] == 1
    instrumentation.deactivate()
    _reset()

def test_passes():
    instrumentation.activate(True)
    import target2
    target2.g()
    target2.A()
    target2.B()
    target2.B.C()


import pytest

from ast_tools import instrumentation
from ast_tools.common import get_ast
from ast_tools import immutable_ast as iast
import target
instrumentation.activate()
import target2

assert target.__ALL__ == target2.__ALL__

@pytest.mark.parametrize("name", target.__ALL__)
def test_basic(name):
    def_g = getattr(target, name)
    def_i = getattr(target2, name)
    g_tree = get_ast(def_g)
    i_tree = instrumentation.INFO[def_i]['ast']
    if isinstance(i_tree, iast.ClassDef):
        # inspect doesn't get the decorator_list for classes
        i_tree = i_tree.replace(decorator_list=())
    assert i_tree == g_tree

@pytest.mark.parametrize("name", target.__ALL__)
def test_env(name):
    seen = {}
    def_ = getattr(target2, name)
    assert set(target2.__ALL__) <= instrumentation.INFO[def_]['env'][0].keys()


def test_closure():
    def_g = target.h()
    def_i = target2.h()
    g_tree = get_ast(def_g)
    i_tree = instrumentation.INFO[def_i]['ast']
    assert i_tree == g_tree
    assert instrumentation.INFO[def_i]['env'][0]['local_var'] == 1


instrumentation.deactivate()

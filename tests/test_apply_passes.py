import inspect

from ast_tools.passes import apply_passes, if_inline
from ast_tools.macros import inline
from ast_tools.common import to_source


def test_apply_with_prologue():
    class foo(apply_passes):
        def prologue(self, tree, env, metadata):
            env.locals['x'] = True
            return tree, env, metadata

    x = False

    @foo([if_inline()])
    def bar():
        if inline(x):
            return 0
        else:
            return 1

    assert inspect.getsource(bar) == '''\
def bar():
    return 0
'''


def test_apply_with_epilogue():
    class foo(apply_passes):
        def epilogue(self, tree, env, metadata):
            expected = """\
@foo([if_inline()])
def bar():
    return 1
"""
            assert to_source(tree) == expected
            return tree, env, metadata

    x = False

    @foo([if_inline()])
    def bar():
        if inline(x):
            return 0
        else:
            return 1

import os
import inspect

import pytest

import ast_tools
from ast_tools.passes import debug, apply_ast_passes, apply_cst_passes
from ast_tools.passes.util import begin_rewrite, end_rewrite
from ast_tools.stack import SymbolTable

def attr_setter(attr):
    def wrapper(fn):
        assert not hasattr(fn, attr)
        setattr(fn, attr, True)
        return fn
    return wrapper

wrapper1 = attr_setter('a')
wrapper2 = attr_setter('b')
wrapper3 = attr_setter('c')

def test_begin_end():
    with pytest.warns(DeprecationWarning):
        @wrapper1
        @end_rewrite(file_name='test_begin_end.py')
        @begin_rewrite()
        @wrapper2
        def foo():
            pass

    assert foo.a
    assert foo.b
    assert inspect.getsource(foo) == '''\
@wrapper1
@wrapper2
def foo():
    pass
'''

@pytest.mark.parametrize('deco', [apply_ast_passes, apply_cst_passes])
def test_apply(deco):
    @wrapper1
    @deco([], file_name='test_apply.py')
    @wrapper2
    def foo():
        pass

    assert foo.a
    assert foo.b
    assert inspect.getsource(foo) == '''\
@wrapper1
@wrapper2
def foo():
    pass
'''


def test_apply_mixed():
    @wrapper1
    @apply_ast_passes([], file_name='test_apply_mixed_ast.py')
    @wrapper2
    @apply_cst_passes([], file_name='test_apply_mixed_cst.py')
    @wrapper3
    def foo():
        pass

    assert foo.a
    assert foo.b
    assert foo.c
    assert inspect.getsource(foo) == '''\
@wrapper1
@wrapper2
@wrapper3
def foo():
    pass
'''

def test_debug(capsys):
    l0 = inspect.currentframe().f_lineno + 1
    @apply_ast_passes(
        [ast_tools.passes.debug(dump_source_filename=True, dump_source_lines=True)],
        debug=True,
        file_name='test_debug.py',
    )
    def foo():
        print("bar")
    out = capsys.readouterr().out
    gold = f"""\
BEGIN SOURCE_FILENAME
{os.path.abspath(__file__)}
END SOURCE_FILENAME

BEGIN SOURCE_LINES
{l0+0}:    @apply_ast_passes(
{l0+1}:        [ast_tools.passes.debug(dump_source_filename=True, dump_source_lines=True)],
{l0+2}:        debug=True,
{l0+3}:        file_name='test_debug.py',
{l0+4}:    )
{l0+5}:    def foo():
{l0+6}:        print("bar")
END SOURCE_LINES

"""
    assert out == gold


def test_debug_error():
    with pytest.raises(
            Exception,
            match=r"Cannot dump source filename without .*"
            ):
        @apply_cst_passes([debug(dump_source_filename=True)])
        def foo():
            print("bar")


    with pytest.raises(
            Exception,
            match=r"Cannot dump source lines without .*"
            ):
        @apply_cst_passes([debug(dump_source_lines=True)])
        def foo():
            print("bar")


def test_custom_env():
    @apply_cst_passes(
        [],
        env=SymbolTable({'x': 1}, globals=globals()),
        file_name='test_custom_env.py',
    )
    def f():
        return x

    assert f() == 1

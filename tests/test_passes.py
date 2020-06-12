import os
import inspect

import pytest

import ast_tools
from ast_tools.passes import begin_rewrite, end_rewrite, debug
from ast_tools.passes import apply_ast_passes, apply_cst_passes
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
    @end_rewrite(file_name='test_debug.py')
    @debug(dump_source_filename=True, dump_source_lines=True)
    @begin_rewrite(debug=True)
    def foo():
        print("bar")
    assert capsys.readouterr().out == f"""\
BEGIN SOURCE_FILENAME
{os.path.abspath(__file__)}
END SOURCE_FILENAME

BEGIN SOURCE_LINES
{l0+0}:    @end_rewrite(file_name='test_debug.py')
{l0+1}:    @debug(dump_source_filename=True, dump_source_lines=True)
{l0+2}:    @begin_rewrite(debug=True)
{l0+3}:    def foo():
{l0+4}:        print("bar")
END SOURCE_LINES

"""


def test_debug_error():

    try:
        @end_rewrite(file_name='test_debug_error.py')
        @debug(dump_source_filename=True)
        @begin_rewrite()
        def foo():
            print("bar")
    except Exception as e:
        assert str(e) == "Cannot dump source filename without @begin_rewrite(debug=True)"

    try:
        @end_rewrite(file_name='test_debug_error.py')
        @debug(dump_source_lines=True)
        @begin_rewrite()
        def foo():
            print("bar")
    except Exception as e:
        assert str(e) == "Cannot dump source lines without @begin_rewrite(debug=True)"


def test_custom_env():
    @end_rewrite(file_name='test_custom_env.py')
    @begin_rewrite(env=SymbolTable({'x': 1}, globals=globals()))
    def f():
        return x

    assert f() == 1


@pytest.mark.parametrize('deco', [apply_ast_passes, apply_cst_passes])
def test_apply_attribute(deco, capsys):
    l0 = inspect.currentframe().f_lineno + 1
    @deco([ast_tools.passes.debug(dump_source_filename=True,
                                  dump_source_lines=True)], debug=True)
    def foo():
        print("bar")
    assert capsys.readouterr().out == f"""\
BEGIN SOURCE_FILENAME
{os.path.abspath(__file__)}
END SOURCE_FILENAME

BEGIN SOURCE_LINES
{l0+0}:    @deco([ast_tools.passes.debug(dump_source_filename=True,
{l0+1}:                                  dump_source_lines=True)], debug=True)
{l0+2}:    def foo():
{l0+3}:        print("bar")
END SOURCE_LINES

"""

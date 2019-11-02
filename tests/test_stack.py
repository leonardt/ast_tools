import pytest
from ast_tools import stack

MAGIC = 'foo'

def test_get_symbol_table():
    MAGIC = 'bar'
    st = stack.get_symbol_table()
    assert st.globals['MAGIC'] == 'foo'
    assert st.locals['MAGIC'] == 'bar'

def test_inspect_symbol_table():
    MAGIC = 'bar'

    @stack.inspect_symbol_table
    def test(st):
        assert st.globals['MAGIC'] == 'foo'
        assert st.locals['MAGIC'] == 'bar'

    test()

    @stack.inspect_symbol_table
    def test(st):
        assert st.locals[stack._SKIP_FRAME_DEBUG_NAME] == 0xdeadbeaf

    stack._SKIP_FRAME_DEBUG_FAIL = True
    exec(stack._SKIP_FRAME_DEBUG_STMT)

    with pytest.raises(RuntimeError):
        test()

    stack._SKIP_FRAME_DEBUG_FAIL = False
    test()


def test_inspect_enclosing_env():
    MAGIC = 'bar'

    @stack.inspect_enclosing_env
    def test(env):
        assert env['MAGIC'] == 'bar'

    test()

    @stack.inspect_enclosing_env
    def test(env):
        assert env[stack._SKIP_FRAME_DEBUG_NAME] == 0xdeadbeaf

    stack._SKIP_FRAME_DEBUG_FAIL = True
    exec(stack._SKIP_FRAME_DEBUG_STMT)

    with pytest.raises(RuntimeError):
        test()

    stack._SKIP_FRAME_DEBUG_FAIL = False
    test()

def test_custom_env():
    def test(env):
        assert env['MAGIC'] == 'bar'

    st = stack.SymbolTable(locals={},globals={'MAGIC':'bar'})
    test = stack.inspect_enclosing_env(test, st=st)
    test()

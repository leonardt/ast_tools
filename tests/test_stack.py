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
    MAGIC1 = 'foo'
    def test(env):
        assert env['MAGIC1'] == 'foo'
        assert env['MAGIC2'] == 'bar'

    st = stack.SymbolTable(locals={},globals={'MAGIC2':'bar'})
    test = stack.inspect_enclosing_env(test, st=st)
    test()

def test_get_symbol_table_copy_frames():
    non_copy_sts = []
    copy_sts = []
    for i in range(5):
        non_copy_sts.append(stack.get_symbol_table())
        copy_sts.append(stack.get_symbol_table(copy_locals=True))
    for j in range(5):
        assert non_copy_sts[j].locals["i"] == 4
        assert copy_sts[j].locals["i"] == j

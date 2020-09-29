from ast_tools.passes import apply_passes, remove_asserts
import inspect

def test_remove_asserts():
    @apply_passes([remove_asserts()])
    def foo():
        if True:
            assert False
        for i in range(10):
            assert i == 0
        assert name_error

    foo()

    assert inspect.getsource(foo) == f'''\
def foo():
    if True:
        pass
    for i in range(10):
        pass
    pass
'''

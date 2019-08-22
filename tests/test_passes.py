import functools
import inspect

from ast_tools.passes import begin_rewrite, end_rewrite



def test_begin_end():
    def wrapper(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapped

    @wrapper
    @end_rewrite()
    @begin_rewrite()
    @wrapper
    def foo():
        pass

    assert inspect.getsource(foo) == '''\
@wrapper
@wrapper
def foo():
    pass
'''

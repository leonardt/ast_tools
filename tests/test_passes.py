import functools
import inspect

from ast_tools.passes import begin_rewrite, end_rewrite, debug



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


def test_debug(capsys):

    @end_rewrite
    @debug(dump_source_filename=True, dump_source_lines=True)
    @begin_rewrite(debug=True)
    def foo():
        print("bar")
    assert capsys.readouterr().out == f"""\
BEGIN SOURCE_FILENAME
{os.path.abspath(__file__)}
END SOURCE_FILENAME

BEGIN SOURCE_LINES
32:    @end_rewrite
33:    @debug(dump_source_filename=True, dump_source_lines=True)
34:    @begin_rewrite(debug=True)
35:    def foo():
36:        print("bar")
END SOURCE_LINES

"""

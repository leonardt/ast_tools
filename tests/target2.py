from ast_tools import passes
from ast_tools.instrumentation import INFO

class debug_begin(passes.begin_rewrite):
    def __call__(self, fn):
        assert fn in INFO
        return super().__call__(fn)

@passes.end_rewrite()
@debug_begin()
def f(): pass

def g():
    @passes.end_rewrite()
    @debug_begin()
    def h(): pass
    return h

@passes.end_rewrite()
@debug_begin()
class A: pass

class B:
    @passes.end_rewrite()
    @debug_begin()
    class C: pass

    @passes.end_rewrite()
    @debug_begin()
    def method(self): pass



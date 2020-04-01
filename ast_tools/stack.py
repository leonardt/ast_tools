'''
Functions and classes the inspect or modify the stack
'''

import copy
import inspect
import typing as tp
import types
import functools
import itertools

from collections import ChainMap
from contextlib import contextmanager
import logging

_SKIP_FRAME_DEBUG_NAME = '_AST_TOOLS_STACK_DEBUG_SKIPPED_FRAME_'
_SKIP_FRAME_DEBUG_VALUE = 0xdeadbeaf
_SKIP_FRAME_DEBUG_STMT = f'{_SKIP_FRAME_DEBUG_NAME} = {_SKIP_FRAME_DEBUG_VALUE}'
_SKIP_FRAME_DEBUG_FAIL = False

class SymbolTable(tp.Mapping[str, tp.Any]):
    locals: tp.MutableMapping[str, tp.Any]
    globals: tp.Dict[str, tp.Any]

    def __init__(self,
            locals: tp.MutableMapping[str, tp.Any],
            globals: tp.Dict[str, tp.Any]):
        self.locals = locals
        self.globals = globals

    def __getitem__(self, key):
        try:
            return self.locals[key]
        except KeyError:
            pass
        return self.globals[key]

    def __iter__(self):
        # the implementation of chain map does things this way
        yield from set().union(self.locals, self.globals)

    def __len__(self):
        return len(set().union(self.locals, self.globals))


def get_symbol_table(
        decorators: tp.Optional[tp.Sequence[inspect.FrameInfo]] = None,
        copy_locals: bool = False
        ) -> SymbolTable:
    exec(_SKIP_FRAME_DEBUG_STMT)
    locals = ChainMap()
    globals = ChainMap()

    if decorators is None:
        decorators = set()
    else:
        decorators = {f.__code__ for f in decorators}
    decorators.add(get_symbol_table.__code__)


    stack = inspect.stack()
    for i in range(len(stack) - 1, 0, -1):
        frame = stack[i]
        if frame.frame.f_code in decorators:
            continue
        debug_check = frame.frame.f_locals.get(_SKIP_FRAME_DEBUG_NAME, None)
        if debug_check == _SKIP_FRAME_DEBUG_VALUE:
            if _SKIP_FRAME_DEBUG_FAIL:
                raise RuntimeError(f'{frame.function} @ {frame.filename}:{frame.lineno} might be leaking names')
            else:
                logging.debug(f'{frame.function} @ {frame.filename}:{frame.lineno} might be leaking names')
        f_locals = stack[i].frame.f_locals
        if copy_locals:
            f_locals = copy.copy(f_locals)
        locals = locals.new_child(f_locals)
        globals = globals.new_child(stack[i].frame.f_globals)
    return SymbolTable(locals=locals, globals=dict(globals))

def inspect_symbol_table(
        fn: tp.Callable, # tp.Callable[[SymbolTable, ...], tp.Any],
        *,
        decorators: tp.Optional[tp.Sequence[inspect.FrameInfo]] = None,
        ) -> tp.Callable:
    exec(_SKIP_FRAME_DEBUG_STMT)
    if decorators is None:
        decorators = ()

    @functools.wraps(fn)
    def wrapped_0(*args, **kwargs):
        exec(_SKIP_FRAME_DEBUG_STMT)
        st = get_symbol_table(list(itertools.chain(decorators, [wrapped_0])))
        return fn(st, *args, **kwargs)
    return wrapped_0


# mostly equivelent to magma.ast_utils.inspect_enclosing_env
def inspect_enclosing_env(
        fn: tp.Callable, # tp.Callable[[tp.Dict[str, tp.Any], ...], tp.Any],
        *,
        decorators: tp.Optional[tp.Sequence[inspect.FrameInfo]] = None,
        st: tp.Optional[SymbolTable] = None) -> tp.Callable:
    exec(_SKIP_FRAME_DEBUG_STMT)
    if decorators is None:
        decorators = ()

    @functools.wraps(fn)
    def wrapped_0(*args, **kwargs):
        exec(_SKIP_FRAME_DEBUG_STMT)

        _st = get_symbol_table(list(itertools.chain(decorators, [wrapped_0])))
        if st is not None:
            _st.locals.update(st)

        env = dict(_st.globals)
        env.update(_st.locals)
        return fn(env, *args, **kwargs)

    return wrapped_0


'''
Functions and classes the inspect or modify the stack
'''

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

class SymbolTable(tp.NamedTuple):
    locals: tp.Mapping[str, tp.Any]
    globals: tp.Dict[str, tp.Any]

def get_symbol_table(
        decorators: tp.Optional[tp.Sequence[inspect.FrameInfo]] = None
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
        locals = locals.new_child(stack[i].frame.f_locals)
        globals = globals.new_child(stack[i].frame.f_globals)
    return SymbolTable(locals=locals, globals=globals)

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
        ) -> tp.Callable:
    exec(_SKIP_FRAME_DEBUG_STMT)
    if decorators is None:
        decorators = ()

    @functools.wraps(fn)
    def wrapped_0(*args, **kwargs):
        exec(_SKIP_FRAME_DEBUG_STMT)
        st = get_symbol_table(list(itertools.chain(decorators, [wrapped_0])))
        env = dict(st.globals)
        env.update(st.locals)
        return fn(env, *args, **kwargs)
    return wrapped_0



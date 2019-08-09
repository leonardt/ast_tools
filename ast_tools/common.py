import ast
import functools
import inspect
import logging
import os
import textwrap
import types
import typing as tp
import weakref

import astor

from ast_tools import stack
from ast_tools.stack import SymbolTable
from ast_tools.visitors import UsedNames

__ALL__ = ['exec_in_file', 'exec_def_in_file', 'get_ast', 'gen_free_name']

DefStmt = tp.Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]

def exec_def_in_file(
        tree: DefStmt,
        st: SymbolTable,
        path: tp.Optional[str] = None,
        file_name: tp.Optional[str] = None) -> None:
    """
    execs a definition in a file and returns the definiton
    """
    if file_name is None:
        file_name = tree.name + '.py'

    exec_in_file(tree, st, path, file_name)
    return st.locals[tree.name]


def exec_in_file(
        tree: ast.AST,
        st: SymbolTable,
        path: tp.Optional[str] = None,
        file_name: tp.Optional[str] = None) -> None:

    """
    execs a definition in a file
    """
    if path is None:
        path = '.ast_tools'
    if file_name is None:
        file_name = f'ast_tools_exec_{hash(tree)}.py'

    source = astor.to_source(tree)
    file_name = os.path.join(path, file_name)
    os.makedirs(path, exist_ok=True)
    with open(file_name, 'w') as fp:
        fp.write(source)

    try:
        code = compile(source, filename=file_name, mode='exec')
    except Exception as e:
        logging.exception("Error compiling source")
        raise e from None

    try:
        exec(code, st.globals, st.locals)
    except Exception as e:
        logging.exception("Error executing code")
        raise e from None


_AST_CACHE = weakref.WeakKeyDictionary()
def get_ast(obj) -> ast.AST:
    """
    Given an object, get the corresponding AST
    """
    try:
        _AST_CACHE[obj]
    except KeyError:
        pass

    src = textwrap.dedent(inspect.getsource(obj))

    if isinstance(obj, types.ModuleType):
        tree = ast.parse(src)
    else:
        tree = ast.parse(src).body[0]

    return _AST_CACHE.setdefault(obj, tree)


def gen_free_name(tree: ast.AST, env: SymbolTable, prefix: str = '__auto_name_'):
    visitor = UsedNames()
    visitor.visit(tree)
    used_names = visitor.names | env.locals.keys() | env.globals.keys()
    f_str = prefix+'{}'
    c = 0
    name = f_str.format(c)
    while name in used_names:
        c += 1
        name = f_str.format(c)

    return name

import abc
import ast
import functools
import inspect
import itertools
import logging
import os
import textwrap
import types
import typing as tp
import weakref

import astor

import libcst as cst

from ast_tools import stack
from ast_tools.stack import SymbolTable
from ast_tools.visitors import used_names
from ast_tools.cst_utils import to_module

__ALL__ = ['exec_in_file', 'exec_def_in_file', 'exec_str_in_file', 'get_ast', 'get_cst', 'gen_free_name']

CSTDefStmt = tp.Union[
        cst.ClassDef,
        cst.FunctionDef,
        ]

ASTDefStmt = tp.Union[
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.FunctionDef,
    ]

DefStmt = tp.Union[ASTDefStmt, CSTDefStmt]

def exec_def_in_file(
        tree: DefStmt,
        st: SymbolTable,
        path: tp.Optional[str] = None,
        file_name: tp.Optional[str] = None,
        serialized_tree: tp.Optional[DefStmt] = None,
        ) -> tp.Any:
    """
    execs a definition in a file and returns the definiton

    For explanation of serialized_tree see
    https://github.com/leonardt/ast_tools/issues/46
    """
    tree_name = _get_name(tree)
    if file_name is None:
        file_name = tree_name + f'{hash(tree)}.py'

    return exec_in_file(tree, st, path, file_name, serialized_tree)[tree_name]

def _get_name(tree: DefStmt) -> str:
    if isinstance(tree, ast.AST):
        return tree.name
    else:
        return tree.name.value

def to_source(
        tree: DefStmt
        ) -> str:
    if isinstance(tree, ast.AST):
        return astor.to_source(tree)
    else:
        return to_module(tree).code

def exec_in_file(
        tree: DefStmt,
        st: SymbolTable,
        path: tp.Optional[str] = None,
        file_name: tp.Optional[str] = None,
        serialized_tree: tp.Optional[DefStmt] = None,
        ) -> tp.MutableMapping[str, tp.Any]:

    """
    execs an ast as a module and returns the modified enviroment

    For explanation of serialized_tree see
    https://github.com/leonardt/ast_tools/issues/46
    """

    source = to_source(tree)
    if serialized_tree is None:
        serialized_source = source
    else:
        serialized_source = to_source(serialized_tree)
    return exec_str_in_file(source, st, path, file_name, serialized_source)


def exec_str_in_file(
        source: str,
        st: SymbolTable,
        path: tp.Optional[str] = None,
        file_name: tp.Optional[str] = None,
        serialized_source: tp.Optional[str] = None,
        ) -> tp.MutableMapping[str, tp.Any]:
    """
    execs a string as a module and returns the modified enviroment

    For explanation of serialized_source see
    https://github.com/leonardt/ast_tools/issues/46
    """

    if path is None:
        path = '.ast_tools'

    if file_name is None:
        file_name = f'ast_tools_exec_{hash(source)}.py'

    if serialized_source is None:
        serialized_source = source

    file_name = os.path.join(path, file_name)
    os.makedirs(path, exist_ok=True)
    with open(file_name, 'w') as fp:
        fp.write(serialized_source)

    try:
        code = compile(source, filename=file_name, mode='exec')
    except Exception as e:
        logging.exception("Error compiling source")
        raise e from None

    st_dict = dict(st)
    try:
        exec(code, st_dict)
        return st_dict
    except Exception as e:
        logging.exception("Error executing code")
        raise e from None


_AST_CACHE: tp.MutableMapping[tp.Any, ast.AST] = weakref.WeakKeyDictionary()
def get_ast(obj) -> ast.AST:
    """
    Given an object, get the corresponding AST
    """
    try:
        return _AST_CACHE[obj]
    except KeyError:
        pass

    src = textwrap.dedent(inspect.getsource(obj))

    if isinstance(obj, types.ModuleType):
        tree = ast.parse(src)
    else:
        tree = ast.parse(src).body[0]

    return _AST_CACHE.setdefault(obj, tree)



_CST_CACHE: tp.MutableMapping[tp.Any, cst.CSTNode] = weakref.WeakKeyDictionary()
def get_cst(obj) -> cst.CSTNode:
    """
    Given an object, get the corresponding CST
    """
    try:
        return _CST_CACHE[obj]
    except KeyError:
        pass

    src = textwrap.dedent(inspect.getsource(obj))

    if isinstance(obj, types.ModuleType):
        tree = cst.parse_module(src)
    else:
        tree = cst.parse_statement(src)

    return _CST_CACHE.setdefault(obj, tree)


def is_free_name(tree: cst.CSTNode, env: SymbolTable, name: str):
    names = used_names(tree)
    return name not in names and name not in env


def is_free_prefix(tree: cst.CSTNode, env: SymbolTable, prefix: str):
    names = used_names(tree)
    return not any(
            name.startswith(prefix)
            for name in itertools.chain(names, env.keys()))


def gen_free_name(
        tree: cst.CSTNode,
        env: SymbolTable,
        prefix: tp.Optional[str] = None) -> str:
    names = used_names(tree) | env.keys()
    if prefix is not None and prefix not in names:
        return prefix
    elif prefix is None:
        prefix = '_auto_name_'

    f_str = prefix+'{}'
    c = 0
    name = f_str.format(c)
    while name in names:
        c += 1
        name = f_str.format(c)

    return name


def gen_free_prefix(
        tree: cst.CSTNode,
        env: SymbolTable,
        preprefix: tp.Optional[str] = None) -> str:
    def check_prefix(prefix: str, used_names: tp.AbstractSet[str]) -> bool:
        return not any(name.startswith(prefix) for name in used_names)

    names = used_names(tree) | env.keys()

    if preprefix is not None and check_prefix(preprefix, names):
        return preprefix
    elif preprefix is None:
        preprefix = '_auto_prefix_'

    f_str = preprefix+'{}'
    c = 0
    prefix = f_str.format(c)
    while not check_prefix(prefix, names):
        c += 1
        prefix = f_str.format(c)

    return prefix

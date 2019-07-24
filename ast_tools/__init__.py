"""
ast_tools top level package
"""
import inspect
import textwrap
import ast

__all__ = ["NameCollector", "collect_names", "get_ast"]

from .collect_names import NameCollector, collect_names


def get_ast(obj):
    """
    Given an object, get the corresponding AST
    """
    indented_program_txt = inspect.getsource(obj)
    program_txt = textwrap.dedent(indented_program_txt)
    return ast.parse(program_txt)

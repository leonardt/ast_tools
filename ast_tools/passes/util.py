from abc import ABCMeta, abstractmethod
import ast
import copy

import inspect
import typing as tp

import libcst as cst

from . import Pass
from . import PASS_ARGS_T

from ast_tools.stack import get_symbol_table, SymbolTable
from ast_tools.common import get_ast, get_cst, exec_def_in_file, exec_str_in_file

__ALL__ = ['begin_rewrite', 'end_rewrite', 'apply_ast_passes']


def _issubclass(t, s) -> bool:
    try:
        return issubclass(t, s)
    except TypeError:
        return False


class _DecoratorStripper(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def get_decorators(tree): pass


    @staticmethod
    @abstractmethod
    def set_decorators(tree, decorators): pass


    @classmethod
    @abstractmethod
    def lookup(cls, node, env): pass


    @classmethod
    def strip(cls, tree, env, start_sentinel, end_sentinel):
        decorators = []
        in_group = False
        first_group = True
        # filter passes from the decorator list
        for node in reversed(cls.get_decorators(tree)):
            if not first_group:
                decorators.append(node)
                continue

            deco = cls.lookup(node, env)
            if in_group:
                if _issubclass(deco, end_sentinel):
                    in_group = False
                    first_group = False
            elif start_sentinel is None or _issubclass(deco, start_sentinel):
                if start_sentinel is end_sentinel:
                    # Just remove current decorator
                    first_group = False
                else:
                    in_group = True
            else:
                decorators.append(node)

        tree = cls.set_decorators(tree, reversed(decorators))
        return tree


class _ASTStripper(_DecoratorStripper):
    @staticmethod
    def get_decorators(tree):
        return tree.decorator_list


    @staticmethod
    def set_decorators(tree, decorators):
        tree = copy.deepcopy(tree)
        tree.decorator_list = decorators
        return tree


    @classmethod
    def lookup(cls, node, env):
        if isinstance(node, ast.Call):
            return cls.lookup(node.func, env)
        elif isinstance(node, ast.Attribute):
            return getattr(cls.lookup(node.value, env), node.attr)
        else:
            assert isinstance(node, ast.Name)
            return env[node.id]


class _CSTStripper(_DecoratorStripper):
    @staticmethod
    def get_decorators(tree):
        return tree.decorators


    @staticmethod
    def set_decorators(tree, decorators):
        return tree.with_changes(decorators=decorators)


    @classmethod
    def lookup(cls, node: cst.CSTNode, env):
        if isinstance(node, cst.Decorator):
            return cls.lookup(node.decorator, env)
        elif isinstance(node, cst.Call):
            return cls.lookup(node.func, env)
        elif isinstance(node, cst.Attribute):
            return getattr(cls.lookup(node.value, env), node.attr.value)
        else:
            assert isinstance(node, cst.Name)
            return env[node.value]

class begin_rewrite:
    """
    begins a chain of passes
    """
    def __init__(self,
                 debug: bool = False,
                 env: tp.Optional[SymbolTable] = None):
        if env is None:
            env = get_symbol_table([self.__init__])

        self.env = env
        self.debug = debug

    def __call__(self, fn) -> PASS_ARGS_T:
        tree = get_ast(fn)
        metadata = {}
        if self.debug:
            metadata["source_filename"] = inspect.getsourcefile(fn)
            metadata["source_lines"] = inspect.getsourcelines(fn)
        return tree, self.env, metadata


class end_rewrite(Pass):
    """
    ends a chain of passes
    """
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> tp.Union[tp.Callable, type]:
        # tree to exec
        etree = _ASTStripper.strip(tree, env, begin_rewrite, None)
        etree = ast.fix_missing_locations(etree)
        # tree to serialize
        stree = _ASTStripper.strip(tree, env, begin_rewrite, end_rewrite)
        stree = ast.fix_missing_locations(stree)
        return exec_def_in_file(etree, env, serialized_tree=stree, **self.kwargs)


class apply_passes(metaclass=ABCMeta):
    '''
    Applies a sequence of passes to a function or class
    '''
    def __init__(self,
                 passes: tp.Sequence[Pass],
                 debug: bool = False,
                 env: tp.Optional[SymbolTable] = None,
                 path: tp.Optional[str] = None,
                 file_name: tp.Optional[str] = None
            ):
        if env is None:
            env = get_symbol_table([self.__init__])
        self.passes = passes
        self.env = env
        self.debug = debug
        self.path = path
        self.file_name = file_name


    @staticmethod
    @abstractmethod
    def parse(self, tree): pass


    @staticmethod
    @abstractmethod
    def strip_decorators(tree): pass


    @abstractmethod
    def exec(self, etree, stree, env): pass


    def __call__(self, fn):
        tree = self.parse(fn)
        metadata = {}
        if self.debug:
            metadata["source_filename"] = inspect.getsourcefile(fn)
            metadata["source_lines"] = inspect.getsourcelines(fn)

        args = tree, self.env, metadata
        for p in self.passes:
            args = p(args)
        tree, env, metadata = args

        etree = self.strip_decorators(tree, env, type(self), None)
        stree = self.strip_decorators(tree, env, type(self), type(self))
        return self.exec(etree, stree, env)


class apply_ast_passes(apply_passes):
    parse = staticmethod(get_ast)
    strip_decorators = staticmethod(_ASTStripper.strip)

    def exec(self, etree: ast.AST, stree: ast.AST, env: SymbolTable):
        etree = ast.fix_missing_locations(etree)
        stree = ast.fix_missing_locations(stree)
        return exec_def_in_file(etree, env, self.path, self.file_name, stree)


class apply_cst_passes(apply_passes):
    parse = staticmethod(get_cst)
    strip_decorators = staticmethod(_CSTStripper.strip)

    def exec(self,
            etree: tp.Union[cst.ClassDef, cst.FunctionDef],
            stree: tp.Union[cst.ClassDef, cst.FunctionDef],
            env: SymbolTable):
        emod = cst.Module(body=(etree,))
        smod = cst.Module(body=(stree,))
        st = exec_str_in_file(emod.code, env, self.path, self.file_name, smod.code)
        return st[etree.name.value]

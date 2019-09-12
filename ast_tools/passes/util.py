import inspect
import ast
import typing as tp

from . import Pass
from . import PASS_ARGS_T
from ast_tools import immutable_ast as iast
from ast_tools.stack import get_symbol_table, SymbolTable
from ast_tools.common import get_ast, exec_def_in_file
from ast_tools.instrumentation import INFO

__ALL__ = ['begin_rewrite', 'end_rewrite']

class begin_rewrite:
    """
    begins a chain of passes
    """
    def __init__(self, debug=False, clean_up=True):
        env = get_symbol_table([self.__init__])
        self.env = env
        self.debug = debug
        self.clean_up = clean_up

    def __call__(self, fn) -> PASS_ARGS_T:
        if fn in INFO:
            info = INFO[fn]
            tree = info['ast']
            self.env = SymbolTable(*info['env'])
            if self.clean_up:
                del INFO[fn]
        else:
            tree = get_ast(fn)
            tree = iast.immutable(tree)

        metadata = {}
        if self.debug:
            metadata["source_filename"] = inspect.getsourcefile(fn)
            metadata["source_lines"] = inspect.getsourcelines(fn)
        return tree, self.env, metadata

def _issubclass(t, s) -> bool:
    try:
        return issubclass(t, s)
    except TypeError:
        return False


class end_rewrite(Pass):
    """
    ends a chain of passes
    """
    def __init__(self, path: tp.Optional[str] = None):
        self.path = path

    def rewrite(self,
            tree: iast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> tp.Union[tp.Callable, type]:

        decorators = []
        first_group = True
        in_group = False
        # filter passes from the decorator list
        for node in reversed(tree.decorator_list):
            if not first_group:
                decorators.append(node)
                continue

            if isinstance(node, iast.Call):
                node_ = node.func
                while isinstance(node_, iast.Attribute):
                    node_=node_.value
            else:
                node_ = node

            assert isinstance(node_, iast.Name), node_
            name = node_.id

            deco = env[name]
            if in_group:
                if  _issubclass(deco, end_rewrite):
                    assert in_group
                    in_group = False
                    first_group = False
            elif _issubclass(deco, begin_rewrite):
                assert not in_group
                in_group = True
            else:
                decorators.append(node)

        tree = tree.replace(decorator_list=tuple(reversed(decorators)))
        return exec_def_in_file(tree, env, self.path)

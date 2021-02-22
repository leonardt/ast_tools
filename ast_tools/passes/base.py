from abc import ABCMeta, abstractmethod
import typing as tp

import libcst as cst

from ast_tools.stack import SymbolTable

__ALL__ = ['Pass', 'PASS_ARGS_T']

PASS_ARGS_T = tp.Tuple[cst.CSTNode, SymbolTable, tp.MutableMapping]


class Pass(metaclass=ABCMeta):
    """
    Abstract base class for passes
    Mostly a convience to unpack arguments
    """

    def __call__(self, args: PASS_ARGS_T) -> PASS_ARGS_T:
        return self.rewrite(*args)

    @abstractmethod
    def rewrite(self,
                tree: cst.CSTNode,
                env: SymbolTable,
                metadata: tp.MutableMapping,
                ) -> PASS_ARGS_T:
        return tree, env, metadata

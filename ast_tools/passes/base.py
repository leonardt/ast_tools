from abc import ABCMeta, abstractmethod
import typing as tp

from ast_tools import immutable_ast as iast
from ast_tools.stack import SymbolTable

__ALL__ = ['Pass', 'PASS_ARGS_T']

PASS_ARGS_T = tp.Tuple[iast.AST, SymbolTable, tp.MutableMapping]

class Pass(metaclass=ABCMeta):
    """
    Abstract base class for passes
    Mostly a convience to unpack arguments
    """

    def __call__(self, args: PASS_ARGS_T) -> PASS_ARGS_T:
        return self.rewrite(*args)

    @abstractmethod
    def rewrite(self,
            env: SymbolTable,
            tree: iast.AST,
            metadata: tp.MutableMapping,
            ) -> PASS_ARGS_T:

        """
        Type annotation here should be followed except on terminal passes e.g.
        end_rewite
        """
        pass

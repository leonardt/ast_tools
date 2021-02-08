import typing as tp
import warnings

import libcst as cst

from . import Pass
from . import PASS_ARGS_T

from ast_tools.common import gen_free_name
from ast_tools.stack import SymbolTable

__ALL__ = ['if_to_phi']


class IfExpTransformer(cst.CSTTransformer):
    def __init__(self, phi_name: str):
        self.phi_name = phi_name

    def leave_IfExp(
            self,
            original_node: cst.IfExp,
            updated_node: cst.IfExp,
            ):
        return cst.Call(
                func=cst.Name(value=self.phi_name),
                args=[
                    cst.Arg(value=v) for v in (
                        updated_node.test,
                        updated_node.body,
                        updated_node.orelse
                    )
                ],
        )

class if_to_phi(Pass):
    '''
    Pass to convert IfExp to call to phi functions
    phi should have signature:
        phi :: Condition -> T -> F -> Union[T, F]
    where:
        Condition is usually bool
        T is the True branch
        F is the False branch
    '''

    def __init__(self,
            phi: tp.Union[tp.Callable, str],
            phi_name_prefix: tp.Optional[str] = None):
        self.phi = phi
        if isinstance(phi, str) and phi_name_prefix is not None:
            warnings.warn('phi_name_prefix has no effect '
                          'if phi is a str', stacklevel=2)
        elif phi_name_prefix is None:
            phi_name_prefix = '__phi'

        self.phi_name_prefix = phi_name_prefix

    def rewrite(self,
            tree: cst.CSTNode,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        if not isinstance(self.phi, str):
            phi_name = gen_free_name(tree, env, self.phi_name_prefix)
            env.locals[phi_name] = self.phi
        else:
            phi_name = self.phi

        visitor = IfExpTransformer(phi_name)
        tree = tree.visit(visitor)
        return tree, env, metadata

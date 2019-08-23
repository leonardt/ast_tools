import ast
import warnings
import typing as tp

from . import Pass
from . import PASS_ARGS_T

from ast_tools.common import gen_free_name
from ast_tools.stack import SymbolTable

__ALL__ = ['if_to_phi']


class IfExpTransformer(ast.NodeTransformer):
    def __init__(self, phi_name: str):
        self.phi_name = phi_name

    def visit_IfExp(self, node: ast.IfExp):
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.orelse)
        return ast.Call(
                func=ast.Name(
                    id=self.phi_name,
                    ctx=ast.Load()
                ),
                args=[test, body, orelse],
                keywords=[]
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
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        if not isinstance(self.phi, str):
            phi_name = gen_free_name(tree, env, self.phi_name_prefix)
            env.locals[phi_name] = self.phi
        else:
            phi_name = self.phi

        visitor = IfExpTransformer(phi_name)
        tree = visitor.visit(tree)

        return tree, env, metadata

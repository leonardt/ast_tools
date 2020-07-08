import ast
import astor
from copy import deepcopy
from collections import Counter
import typing as tp
import warnings

from . import Pass
from . import PASS_ARGS_T

from ast_tools.common import gen_free_prefix, gen_free_name, is_free_name
from ast_tools.immutable_ast import immutable, mutable
from ast_tools.stack import SymbolTable
from ast_tools.transformers.node_replacer import NodeReplacer
from ast_tools.visitors.node_finder import NodeFinder

__all__ = ['cse']

def _is_leaf_expr(node: ast.expr):
    assert isinstance(nod, ast.expr)

    return isinstance(node,(
        ast.Attribute,
        ast.Constant,
        ast.Name,
        ast.NameConstant,
        ast.Num,
        ast.Subscript,
        ))

class ExprFinder(NodeFinder):
    def _get_key(self, node):
        if isinstance(node, ast.expr):
            # Need the immutable value so its comparable
            return immutable(node)
        else:
            return None

class ExprReplacer(NodeReplacer):
    def _get_key(self, node):
        if isinstance(node, ast.expr):
            # Need the immutable value so its comparable
            return immutable(node)
        else:
            return None

class ExprCounter(ast.NodeVisitor):
    def __init__(self):
        self.cses = Counter()

    def visit_UnaryOp(self, node: ast.UnaryOp):
        self.cses[immutable(node)] += 1
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        self.cses[immutable(node)] += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        self.cses[immutable(node)] += 1
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        self.cses[immutable(node)] += 1
        self.generic_visit(node)

    def visit_IfExpr(self, node: ast.IfExp):
        self.cses[immutable(node)] += 1
        self.generic_visit(node)

    def vist_Call(self, node: ast.Call):
        # this seems hard to get right so not going to save Calls
        return self.generic_visit(node)


class CSEElim(ast.NodeTransformer):
    '''Eliminates a  CSE'''
    # this could probably be more effecient by handling multiple CSES at
    # a time but this is simple

    def __init__(self,
            cse,
            cse_name):

        self.cse = cse
        self.cse_name = cse_name
        self.recorded = False
        self.root = None
        self.replacer = ExprReplacer({})
        self.replacer.add_replacement(cse, ast.Name(cse_name, ast.Load()))

    def visit(self, node: ast.AST) -> ast.AST:
        # basically want to able to visit a top level def
        # but don't want to generally recurse into them
        # also want to change behavior after recording the cse
        if self.root is None:
            self.root = node
            return super().generic_visit(node)
        elif self.recorded:
            return self.replacer.visit(node)
        else:
            return super().visit(node)


    def visit_Assign(self, node):
        assert not self.recorded
        finder = ExprFinder(self.cse)
        finder.visit(node)
        if finder.target is not None:
            self.recorded = True
            # eliminate the node from the expression
            rest = self.replacer.visit(node)
            save = ast.Assign(
                        targets=[ast.Name(self.cse_name, ast.Store())],
                        value=deepcopy(self.cse))
            return [save, rest]
        else:
            return super().generic_visit(node)

    # don't support control flow (assumes ssa)
    def visit_If(self, node: ast.If):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_For(self, node: ast.For):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_AsyncFor(self, node: ast.AsyncFor):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_While(self, node: ast.While):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_With(self, node: ast.With):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_AsyncWith(self, node: ast.AsyncWith):
        raise SyntaxError(f"Cannot handle node {node}")

    def visit_Try(self, node: ast.Try):
        raise SyntaxError(f"Cannot handle node {node}")

    # don't recurs into defs
    def visit_ClassDef(self, node: ast.ClassDef):
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return node


class cse(Pass):
    '''
    Performs common subexpression elimination

    Most be run after ssa.

    Post bool_to_bit will likely eliminate more as:
        `a and b and c`
    is a single `BoolOp`  but
        `a & b & c`
    is:
        `(a & b) & c`

    this means `a and b` is not a subexpression of `a and b and c`
    but `a & b` is a subexpression of `a & b & c`
    '''
    def __init__(self,
            cse_prefix: str = '__common_expr'):
        self.cse_prefix = cse_prefix


    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        prefix = gen_free_prefix(tree, env, self.cse_prefix)
        c = 0
        while True:
            counter = ExprCounter()
            counter.visit(tree)
            if not counter.cses:
                break

            expr, freq = counter.cses.most_common()[0]
            if freq <= 1:
                break

            expr = mutable(expr)
            elim = CSEElim(expr, prefix + repr(c))
            c += 1
            tree = elim.visit(tree)


        return tree, env, metadata

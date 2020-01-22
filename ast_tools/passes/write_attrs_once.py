import ast
from copy import deepcopy
import itertools
import typing as tp

from . import Pass
from . import PASS_ARGS_T

from ast_tools.common import gen_free_name, is_free_name
from ast_tools.stack import SymbolTable
from ast_tools.visitors import collect_targets
from ast_tools.transformers.node_replacer import NodeReplacer
from ast_tools.immutable_ast import immutable, mutable
from .ssa import _always_returns

__ALL__ = ['write_attrs_once']

class AttrReplacer(NodeReplacer):
    def _get_key(self, node):
        if isinstance(node, ast.Attribute):
            # Need the immutable value so its comparable
            return immutable(node.value), node.attr
        else:
            return None


class InsertWrites(ast.NodeTransformer):
    def __init__(self, writes):
        self.writes = writes

    def visit_Return(self, node: ast.Return):
        return [*self.writes, node]


class write_attrs_once(Pass):
    def rewrite(self,
            tree: ast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        if not isinstance(tree, ast.FunctionDef):
            raise NotImplementedError('Only supports rewriting of functions')


        targets = collect_targets(tree, ast.Attribute)
        attr_table = {}
        replacer = AttrReplacer(attr_table)
        for t in targets:
            if not isinstance(t.value, ast.Name):
                raise NotImplementedError(f'Only supports writing attributes '
                                          f'of Name not {type(t.value)}')
            else:
                name = ast.Name(
                        id=gen_free_name(tree, env, '_'.join((t.value.id, t.attr))),
                        ctx=ast.Load())
                replacer.add_replacement(t, name)

        tree = replacer.visit(tree)
        reads = []
        writes = []
        for key, replacement in attr_table.items():
            read = ast.Assign(
                targets=[
                    ast.Name(replacement.id, ast.Store())
                ],
                value=ast.Attribute(
                    value=mutable(key[0]),
                    attr=key[1],
                    ctx=ast.Load()
                )
            )

            write = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=mutable(key[0]),
                        attr=key[1],
                        ctx=ast.Store(),
                    )
                ],
                value=deepcopy(replacement)
            )

            reads.append(read)
            writes.append(write)

        if _always_returns(tree.body):
            tree.body = reads + tree.body
        else:
            tree.body = reads + tree.body + writes

        inserter = InsertWrites(writes)
        tree = inserter.visit(tree)
        return tree, env, metadata

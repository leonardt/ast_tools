import ast
from copy import deepcopy


class SymbolReplacer(ast.NodeTransformer):
    def __init__(self, symbol_table):
        self.symbol_table = symbol_table

    def visit_Name(self, node):
        if node.id in self.symbol_table:
            # TODO: Remove deepcopy once immutable ast is merged
            return deepcopy(self.symbol_table[node.id])
        return node


def replace_symbols(tree, symbol_table):
    return SymbolReplacer(symbol_table).visit(tree)

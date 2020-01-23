import ast
from .node_replacer import NodeReplacer

class SymbolReplacer(NodeReplacer):
    def _get_key(self, node):
        if isinstance(node, ast.Name):
            return node.id
        else:
            return None

def replace_symbols(tree, symbol_table):
    return SymbolReplacer(symbol_table).visit(tree)

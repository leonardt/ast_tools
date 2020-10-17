import libcst as cst

from .node_replacer import NodeReplacer

class SymbolReplacer(NodeReplacer):
    def _get_key(self, node: cst.CSTNode):
        if isinstance(node, cst.Name):
            return node.value
        else:
            return None

def replace_symbols(tree, symbol_table):
    return tree.visit(SymbolReplacer(symbol_table))

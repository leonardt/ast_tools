import typing as tp

from ast_tools import immutable_ast as iast

class Renamer(iast.NodeTransformer):
    def __init__(self, name_map: tp.Mapping[str, str]):
        self.name_map = name_map

    def visit_Name(self, node):
        name = node.id
        new_name = self.name_map.setdefault(name, name)
        return iast.Name(
                id=new_name,
                ctx=node.ctx,
            )

import ast
import typing as tp


class Renamer(ast.NodeTransformer):
    def __init__(self, name_map: tp.Mapping[str, str]):
        self.name_map = name_map

    def visit_Name(self, node):
        name = node.id
        new_name = self.name_map.setdefault(name, name)
        return ast.copy_location(
            ast.Name(
                id=new_name,
                ctx=node.ctx,
            ),
            node,
        )

import importlib
import importlib.abc
import importlib.machinery
import os
import types
import sys

from ast_tools.stack import SymbolTable
from ast_tools.common import exec_tree_in_file
from ast_tools import immutable_ast as iast
__ALL__ = ['module_passes', 'RewriteImporter']

module_passes = []

class RewriteImporter(
        importlib.machinery.PathFinder,
        importlib.abc.Loader):

    @classmethod
    def find_spec(cls, fullname, path, target=None):
        spec = super().find_spec(fullname, path, target)
        if spec is not None:
            spec.loader = cls
        return spec


    @classmethod
    def create_module(cls, spec):
        module = types.ModuleType(spec.name)
        module.__spec__ = spec
        module.__name__ = spec.name
        module.__loader__ = spec.loader
        module.__file__ = spec.origin
        module.__path__ = spec.submodule_search_locations
        module.__cached__ = spec.cached
        module.__package__ = spec.parent
        return module

    @classmethod
    def exec_module(cls, module):
        src_file = module.__file__
        with open(src_file, 'rb') as src:
            src_code = src.read()

        tree = iast.parse(src_code)
        env = SymbolTable(module.__dict__, module.__dict__)
        metadata = {}

        for pass_ in module_passes:
            tree, env, metadata = pass_.rewrite(tree, env, metadata)

        module.__dict__.update(exec_tree_in_file(tree, env, file_name=os.path.basename(src_file)))


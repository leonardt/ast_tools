import typing as tp
import weakref

from ast_tools import immutable_ast as iast
from ast_tools.common import gen_free_name
from ast_tools.stack import SymbolTable
from . import Pass
from . import PASS_ARGS_T
import sys

INFO = weakref.WeakKeyDictionary()

def dump_with_module(tree: iast.AST, module: str):
    '''
    Basically dump but prepend module to class names
    so that it can be eval'ed:
        import ast
        from ast_tools import immutable_ast as iast
        t = ast.parse(...)
        t2 = eval(dump_with_module(t, 'ast'))
        assert iast.immutable(t) == iast.immutable(t2)
    '''
    head = f'{module}.{type(tree).__name__}('
    tail = ')'
    body = []
    for field, value in iast.iter_fields(tree):
        if isinstance(value, iast.AST):
            value = dump_with_module(value, module)
        elif isinstance(value, iast.S_NODE):
            value = (dump_with_module(e, module) for e in value)
            value = '[' + ', '.join(value) + ']'
        else:
            value = repr(value)
        body.append(f'{field}={value}')
    body = ', '.join(body)

    return head + body + tail


class Instrumentator(iast.NodeTransformer):
    def __init__(self, import_name, store_env):
        self.import_name = import_name
        self.store_env = store_env

    def handle_def(self, node: iast.stmt):
        new_node = self.generic_visit(node)

        # import ast_tools
        import_node = iast.Import(
            names=[iast.alias('ast_tools', self.import_name)]
        )

        # store the ast
        args =[dump_with_module(node, self.import_name + '.immutable_ast')]
        if self.store_env:
            # store the env
            args.append('(locals(), globals())')

        args = ', '.join(args)
        mark = f'{self.import_name}.passes.instrumentation.mark'
        mark_node = iast.parse(f'{mark}({args})').body[0].value
        assert isinstance(mark_node, iast.Call)
        #decorate the new_node with mark
        new_node = new_node.replace(decorator_list=new_node.decorator_list+(mark_node,))


        # del ast_tools
        del_node = iast.Delete(targets=[
            iast.Name(self.import_name,  iast.Del()),
            ])

        return [import_node, new_node, del_node]


    def visit_ClassDef(self, node: iast.ClassDef):
        return self.handle_def(node)

    def visit_FunctionDef(self, node: iast.FunctionDef):
        return self.handle_def(node)

    def visit_AsyncFunctionDef(self, node: iast.AsyncFunctionDef):
        return self.handle_def(node)

class InstrumentationPass(Pass):
    def __init__(self, store_env: bool):
        self.store_env = store_env

    def rewrite(self,
            tree: iast.AST,
            env: SymbolTable,
            metadata: tp.MutableMapping,
            ) -> PASS_ARGS_T:
        import_name = gen_free_name(tree, env, 'ast_tools')
        instrumentator = Instrumentator(import_name, self.store_env)
        tree = instrumentator.visit(tree)
        return tree, env, metadata

def mark(tree, env=None):
    def wrapper(obj):
        if env is not None:
            INFO[obj] = {'ast': tree, 'env': env}
        else:
            INFO[obj] = {'ast': tree}

        return obj
    return wrapper

import ast
import astor

from ast_tools.common import get_ast, gen_free_name, gen_free_prefix
from ast_tools.stack import SymbolTable
from ast_tools.passes import begin_rewrite, end_rewrite


def test_get_ast():
    def f(): pass
    f_str = 'def f(): pass'
    ast_str_0 = astor.dump_tree(get_ast(f))
    ast_str_1 = astor.dump_tree(ast.parse(f_str).body[0])
    assert ast_str_0 == ast_str_1


def test_gen_free_name():
    src = '''
class P:
    P5 = 1
    def __init__(self): self.y = 0
def P0():
    return P.P5
P1 = P0()
'''
    tree = ast.parse(src)
    env = SymbolTable({}, {})

    free_name = gen_free_name(tree, env)
    assert free_name == '__auto_name_0'

    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P2'
    env = SymbolTable({'P3': 'foo'}, {})
    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P2'
    env = SymbolTable({'P3': 'foo'}, {'P2' : 'bar'})
    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P4'

def test_gen_free_prefix():
    src = '''
class P:
    P5 = 1
    def __init__(self): self.y = 0
def P0():
    return P.P5
P1 = P0()
'''
    tree = ast.parse(src)
    env = SymbolTable({}, {})

    free_prefix = gen_free_prefix(tree, env)
    assert free_prefix == '__auto_prefix_0'

    free_prefix = gen_free_prefix(tree, env, 'P')
    assert free_prefix == 'P2'

def test_exec_in_file():
    x = 3
    def foo():
        return x
    assert foo() == 3

    @end_rewrite()
    @begin_rewrite()
    def foo():
        return x

    assert foo() == 3

import ast
import astor

from ast_tools.common import get_ast, gen_free_name, SymbolTable


def test_get_ast():
    def f(): pass
    f_str = 'def f(): pass'
    ast_str_0 = astor.dump_tree(get_ast(f))
    ast_str_1 = astor.dump_tree(ast.parse(f_str).body[0])
    assert ast_str_0 == ast_str_1


def test_gen_free():
    src = '''
class P0:
    P5 = 1
    def __init__(self): self.y = 0
def P1():
    return P0.P5
P2 = P1()
'''
    tree = ast.parse(src)
    env = SymbolTable({}, {})
    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P3'
    env = SymbolTable({'P4': 'foo'}, {})
    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P3'
    env = SymbolTable({'P4': 'foo'}, {'P3' : 'bar'})
    free_name = gen_free_name(tree, env, prefix='P')
    assert free_name == 'P5'

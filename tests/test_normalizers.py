import libcst as cst

import pytest

from ast_tools.cst_utils import to_module
from ast_tools.transformers.normalizers import ElifToElse
from ast_tools.transformers.normalizers import NormalizeBlocks
from ast_tools.transformers.normalizers import NormalizeLines

def test_elif_to_else():
    src = '''\
if x:
    foo()
elif y:
    bar()
else:
    foo_bar()
'''

    gold_src = '''\
if x:
    foo()
else:
    if y:
        bar()
    else:
        foo_bar()
'''

    tree = cst.parse_statement(src)
    norm = tree.visit(ElifToElse())
    gold = cst.parse_statement(gold_src)
    assert norm.deep_equals(gold)


def test_normalize_blocks_if():
    src = '''\
if x: foo()
elif y: bar()
else: foo_bar()
'''

    gold_src = '''\
if x:
    foo()
elif y:
    bar()
else:
    foo_bar()
'''

    tree = cst.parse_statement(src)
    norm = tree.visit(NormalizeBlocks())
    gold = cst.parse_statement(gold_src)
    assert norm.deep_equals(gold)

def test_normalize_blocks_def():
    src = '''\
def f(): return 0
'''

    gold_src = '''\
def f():
    return 0
'''

    tree = cst.parse_statement(src)
    norm = tree.visit(NormalizeBlocks())
    gold = cst.parse_statement(gold_src)
    assert norm.deep_equals(gold)

def test_normalize_lines_module():
    src = '''\
x = 1;y = 2
'''

    gold_src = '''\
x = 1;
y = 2
'''

    tree = cst.parse_module(src)
    norm = tree.visit(NormalizeLines())
    gold = cst.parse_module(gold_src)
    assert norm.deep_equals(gold)

def test_normalize_lines_block():

    src = '''\
if x:
    y = 0;z = 1
'''

    gold_src = '''\
if x:
    y = 0;
    z = 1
'''

    tree = cst.parse_statement(src)
    norm = tree.visit(NormalizeLines())
    gold = cst.parse_statement(gold_src)
    assert norm.deep_equals(gold)


def test_normalize_lines_partial():
    src = '''\
if x: y = 0;z = 0
else: z = 1
'''

    gold_src = '''\
if x:
    y = 0;
    z = 0
else: z = 1
'''

    tree = cst.parse_statement(src)
    norm = tree.visit(NormalizeLines())
    gold = cst.parse_statement(gold_src)
    norm_code = to_module(norm).code
    gold_code = to_module(gold).code
    assert norm.deep_equals(gold)


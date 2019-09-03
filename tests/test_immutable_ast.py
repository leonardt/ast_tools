import pytest
import ast

import inspect
from ast_tools import immutable_ast as iast
from ast_tools.immutable_ast import ImmutableMeta


trees = []

# inspect is about the largest module I know
# hopefully it has a diverse ast
for mod in (iast, inspect, ast, pytest):
    with open(mod.__file__, 'r') as f:
        text = f.read()
    tree = ast.parse(text)
    trees.append(tree)


@pytest.mark.parametrize("tree", trees)
def test_mutable_to_immutable(tree):
    def _test(tree, itree):
        if isinstance(tree, ast.AST):
            assert isinstance(itree, iast.AST)
            assert isinstance(tree, type(itree))
            assert tree._fields == itree._fields
            assert ImmutableMeta._mutable_to_immutable[type(tree)] is type(itree)
            for field, value in ast.iter_fields(tree):
                _test(value, getattr(itree, field))
        elif isinstance(tree, list):
            assert isinstance(itree, tuple)
            assert len(tree) == len(itree)
            for c, ic in zip(tree, itree):
                _test(c, ic)
        else:
            assert tree == itree


    itree = iast.immutable(tree)
    _test(tree, itree)

@pytest.mark.parametrize("tree", trees)
def test_immutable_to_mutable(tree):
    def _test(tree, mtree):
        assert type(tree) is type(mtree)
        if isinstance(tree, ast.AST):
            for field, value in ast.iter_fields(tree):
                _test(value, getattr(mtree, field))
        elif isinstance(tree, list):
            assert len(tree) == len(mtree)
            for c, mc in zip(tree, mtree):
                _test(c, mc)
        else:
            assert tree == mtree

    itree = iast.immutable(tree)
    mtree = iast.mutable(itree)
    _test(tree, mtree)


@pytest.mark.parametrize("tree", trees)
def test_eq(tree):
    itree = iast.immutable(tree)
    jtree = iast.immutable(tree)
    assert itree == jtree
    assert hash(itree) == hash(jtree)

def test_mutate():
    node = iast.Name(id='foo', ctx=iast.Load())
    # can add metadata to a node
    node.random = 0
    del node.random

    # but cant change its fields
    for field in node._fields:
        with pytest.raises(AttributeError):
            setattr(node, field, 'bar')

        with pytest.raises(AttributeError):
            delattr(node, field)


def test_construct_from_mutable():
    node = iast.Module([
            ast.Name(id='foo', ctx=ast.Store())
        ])

    assert isinstance(node.body, tuple)
    assert type(node.body[0]) is iast.Name
    assert type(node.body[0].ctx) is iast.Store


class visit_tester(iast.NodeVisitor):
    def __init__(self, py):
        self.order = []
        self.py = py

    def visit(self, node):
        assert isinstance(node, iast.AST)
        if self.py:
            assert isinstance(node, ast.AST)
            self.order.append(iast.immutable(node))
        else:
            assert not isinstance(node, ast.AST)
            self.order.append(node)

        self.generic_visit(node)

class pyvisitor(ast.NodeVisitor):
    def __init__(self):
        self.order = []
        self.py = True

    visit = visit_tester.visit

def test_visitor():
    # show that iast.NodeVisitor can operate on regular trees
    mtree = trees[0]
    itree = iast.immutable(mtree)

    pvisitor = pyvisitor()
    mvisitor = visit_tester(True)
    ivisitor = visit_tester(False)

    pvisitor.visit(mtree)
    mvisitor.visit(mtree)
    ivisitor.visit(itree)

    assert pvisitor.order == mvisitor.order
    assert mvisitor.order == ivisitor.order

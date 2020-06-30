import pytest
import ast
import sys

import inspect
from ast_tools import immutable_ast
from ast_tools.immutable_ast import ImmutableMeta


trees = []

# inspect is about the largest module I know
# hopefully it has a diverse ast
for mod in (immutable_ast, inspect, ast, pytest):
    with open(mod.__file__, 'r') as f:
        text = f.read()
    tree = ast.parse(text)
    trees.append(tree)


@pytest.mark.parametrize("tree", trees)
def test_mutable_to_immutable(tree):
    def _test(tree, itree):
        if isinstance(tree, ast.AST):
            assert isinstance(itree, immutable_ast.AST)
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


    itree = immutable_ast.immutable(tree)
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

    itree = immutable_ast.immutable(tree)
    mtree = immutable_ast.mutable(itree)
    _test(tree, mtree)


@pytest.mark.parametrize("tree", trees)
def test_eq(tree):
    itree = immutable_ast.immutable(tree)
    jtree = immutable_ast.immutable(tree)
    assert itree == jtree
    assert hash(itree) == hash(jtree)

def test_mutate():
    node = immutable_ast.Name(id='foo', ctx=immutable_ast.Load())
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
    asts = [ast.Name(id='foo', ctx=ast.Store())]
    node = (
        immutable_ast.Module(asts)
        if sys.version_info < (3, 8)
        else immutable_ast.Module(asts, type_ignores=None)
    )

    assert isinstance(node.body, tuple)
    assert type(node.body[0]) is immutable_ast.Name
    assert type(node.body[0].ctx) is immutable_ast.Store

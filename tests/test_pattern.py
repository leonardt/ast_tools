import ast

from ast_tools.pattern import ast_match
from ast_tools.common import get_ast


def parse_match(pattern, stmt):
    return ast_match(pattern, ast.parse(stmt).body[0])


def test_pattern_assign_copy():
    stmt1 = "x = y"
    stmt2 = "x = 1"

    pattern = "{lhs:Name} = {rhs:Name}"
    match1 = parse_match(pattern, stmt1)
    assert match1 is not None
    assert match1['lhs'].id == 'x'
    assert match1['rhs'].id == 'y'

    match2 = parse_match(pattern, stmt2)
    assert match2 is None


def test_pattern_assign_number():
    stmt1 = "x = y"
    stmt2 = "x = 1"

    pattern = "{lhs:Name} = {rhs:Num}"
    match1 = parse_match(pattern, stmt1)
    assert match1 is None

    match2 = parse_match(pattern, stmt2)
    assert match2 is not None
    assert match2['lhs'].id == 'x'
    assert match2['rhs'].n == 1


def test_pattern_if():
    stmt1 = """
if x:
    y = 1
else:
    z = 1
"""

    stmt2 = """
if x:
    print(y)
else:
    z = 1
"""

    pattern = """
if {cond:Name}:
    {then_:Assign}
else:
    {else_}
"""

    match1 = parse_match(pattern, stmt1)
    assert match1 is not None

    match2 = parse_match(pattern, stmt2)
    assert match2 is None

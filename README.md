[![Build Status](https://travis-ci.com/leonardt/ast_tools.svg?branch=master)](https://travis-ci.com/leonardt/ast_tools)
[![Coverage Status](https://coveralls.io/repos/github/leonardt/ast_tools/badge.svg?branch=master)](https://coveralls.io/github/leonardt/ast_tools?branch=master)

Toolbox for working with the Python AST

```
pip install ast_tools
```

# Useful References
* [Green Tree Snakes - the missing Python AST docs](greentreesnakes.readthedocs.io/)


# Macros
## Loop Unrolling
Unroll loops using the pattern
```python
for <var> in ast_tools.macros.unroll(<iter>):
    ...
```

`<iter>` should be an iterable object that produces integers (e.g. `range(8)`)
that can be evaluated at definition time (can refer to variables in the scope
of the function definition)

For example, 
```python
@end_rewrite()
@loop_unroll()
@begin_rewrite()
def foo():
    for i in ast_tools.macros.unroll(range(8)):
        print(i)
```
is rewritten into
```python
def foo():
    print(0)
    print(1)
    print(2)
    print(3)
    print(4)
    print(5)
    print(6)
    print(7)
```

You can also use a list of `int`s, here's an example that also uses a reference
to a variable defined in the outer scope:
```python
j = [1, 2, 3]
@end_rewrite()
@loop_unroll()
@begin_rewrite()
def foo():
    for i in ast_tools.macros.unroll(j):
        print(i)
```
becomes
```python
def foo():
    print(1)
    print(2)
    print(3)
```

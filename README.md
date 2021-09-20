[![Build Status](https://travis-ci.com/leonardt/ast_tools.svg?branch=master)](https://travis-ci.com/leonardt/ast_tools)
[![Coverage Status](https://coveralls.io/repos/github/leonardt/ast_tools/badge.svg?branch=master)](https://coveralls.io/github/leonardt/ast_tools?branch=master)

Toolbox for working with the Python AST

```
pip install ast_tools
```

# Useful References
* [Green Tree Snakes - the missing Python AST docs](https://greentreesnakes.readthedocs.io/)


# Passes
ast_tools provides a number of passes for rewriting function and classes (could
also work at the module level however no such pass exists). Passes are
applied with the `apply_passes` decorator:

```python
@apply_passes([pass1(), pass2()])
def foo(...): ...
```
Each pass takes as arguments an AST, an environment, and metadata and
returns (possibly) modified versions of each.
`apply_passes` begins a chain of rewrites by first looking
up the ast of the decorated object and gather attempts to gather locals
and globals from the call site to build the environment.

After all rewrites have run `apply_passes` serializes and
execute the rewritten ast.

## Know Issues
### Collecting the AST
`apply_passes` relies on `inspect.getsource` to get the
source of the decorated definition (which is then parsed to get the initial ast).
However, `inspect.getsource` has many limitations.

### Collecting the Environment
`apply_passes` does its best to infer the environment
however there is no way to do this in a fully correct way.  Users are
encouraged to pass environment explicitly:
```python
@apply_passes(..., env=SymbolTable(locals(), globals()))
def foo(...): ...
```

### Wrapping the apply_passes decorator
The `apply_passes` decorator must not be wrapped.

As decorators are a part of the AST of the object they are applied to
they must be removed from the rewritten AST before it is executed.  If they
are not removed rewrites will recurse infinitely as

```python
@apply_passes([...])
def foo(...): ...
```

would become

```python
exec('''\
@apply_passes([...])
def rewritten_foo(...): ...
''')
```
Note: this would invoke `apply_passes([...])` on `rewritten_foo`

To avoid this the `apply_passes` decorator filters itself from the decorator list.  If, however,
the decorator is wrapped inside another decorator, this will fail.

### Inner decorators are called multiple times

Decorators that are applied before a rewrite group will be called multiple times.
See https://github.com/leonardt/ast_tools/issues/46 for detailed explanation.
To avoid this users are encouraged to make rewrites the inner most decorators
when possible.

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
from ast_tools.passes import apply_passes, loop_unroll

@apply_passes([loop_unroll()])
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
from ast_tools.passes import apply_passes, loop_unroll

j = [1, 2, 3]
@apply_passes([loop_unroll()])
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

## Inlining If Statements
This macro allows you to evaluate `if` statements at function definition time,
so the resulting rewritten function will have the `if` statements marked
"inlined" removed from the final code and replaced with the chosen branch based
on evaluating the condition in the definition's enclosing scope.  `if`
statements are marked by using the form `if inline(...):` where `inline` is
imported from the `ast_tools.macros` package.  `if` statements not matching
this pattern will be ignored by the rewrite logic.

Here's an example
```python
from ast_tools.macros import inline
from ast_tools.passes import apply_passes, if_inline

y = True

@apply_passes([if_inline()])
def foo(x):
    if inline(y):
        return x + 1
    else:
        return x - 1


import inspect
assert inspect.getsource(foo) == f"""\
def foo(x):
    return x + 1
"""
```

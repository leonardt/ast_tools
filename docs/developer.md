# Adding passes
The `ast_tools` library is designed around the `apply_passes` decorator that is
used as follows:
```python
@apply_passes([pass1(), pass2()])
def foo(...): ...
```

The simplest way to extend the library is to define a new pass that works with
this decorator.  This is achieved by subclassing the `Pass` abstract class, see
the definition
[here](https://github.com/leonardt/ast_tools/blob/master/ast_tools/passes/base.py#L13).

The essential method is the `rewrite` method:
```python
    def rewrite(self,
                tree: cst.CSTNode,
                env: SymbolTable,
                metadata: tp.MutableMapping,
                ) -> PASS_ARGS_T:
        return tree, env, metadata
```

There are three arguments:
1. `tree` -- the CST (from [libcst](https://libcst.readthedocs.io/en/latest/))
   of the function being rewritten.
2. `env` -- the environment of the function being rewritten (the `SymbolTable`
   class is defined
   [here](https://github.com/leonardt/ast_tools/blob/master/ast_tools/stack.py#L21)
   ).
3. `metadata` -- a mapping containing arbitrary information either provided by
   the user or previous passes

Each of these three arguments must be returned in the same order from the `rewrite` method.

The ordering of passes is defined by the arguments to `apply_passes` and each
pass will be called with the latest `tree`, `env`, and `metadata`.  Passes can
share information using the `metadata` mapping, and can update the `env` that
will be used to execute the final `tree`.

## Pass Examples

The [loop unrolling
pass](https://github.com/leonardt/ast_tools/blob/master/ast_tools/passes/loop_unroll.py)
is quite simple, with most of its logic dispatching to the [loop unroller
transformer](https://github.com/leonardt/ast_tools/blob/master/ast_tools/transformers/loop_unroller.py).
For more information on how to write a `Transformer`, see the [libcst
documentation](https://libcst.readthedocs.io/en/latest/tutorial.html#Build-Visitor-or-Transformer).
Notice that the transformer relies on the `env` table to evaluate the unroll
arguments.

The
[if_inliner](https://github.com/leonardt/ast_tools/blob/master/ast_tools/transformers/if_inliner.py)
transformer is another good place to start, which similarly relies on the `env`
to evaluate `if` statements at "macro" time.

After reviewing these examples, you're ready to look at the full suite of
standard
[passes](https://github.com/leonardt/ast_tools/tree/master/ast_tools/passes)
and
[transformers](https://github.com/leonardt/ast_tools/tree/master/ast_tools/transformers).

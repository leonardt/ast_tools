import typing as tp
import types

import libcst as cst
import functools as ft

from ast_tools.common import gen_free_prefix
from ast_tools.cst_utils import InsertStatementsVisitor, DeepNode
from ast_tools.metadata.condition_provider import ConditionProvider

__ALL__ = ['ssa']


class trace:
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, objtype=None):
        if obj is not None:
            return types.MethodType(self.f, obj)
        else:
            return self.f

    def __set_name__(self, owner, name):
        f = self.f
        @ft.wraps(f)
        def wrapper(*args, **kwargs):
            print(f'calling: {owner.__name__}.{name}')
            return f(*args, **kwargs)

        self.f = wrapper

class AlwaysReturnsProvider(cst.BatchableMetadataProvider[bool]):
    def _visit_simple_block(self,
            node: tp.Union[cst.SimpleStatementLine, cst.SimpleStatementSuite]
            ) -> tp.Optional[bool]:
        for child in node.body:
            if isinstance(child, cst.Return):
                self.set_metadata(node, True)
                return False
        self.set_metadata(node, False)
        return False

    def visit_SimpleStatementLine(self,
            node: cst.SimpleStatementLine,
            ) -> tp.Optional[bool]:
        return self._visit_simple_block(node)

    def visit_SimpleStatementSuite(self,
            node: cst.SimpleStatementLine,
            ) -> tp.Optional[bool]:
        return self._visit_simple_block(node)

    def leave_IndentedBlock(self, node: cst.IndentedBlock) -> None:
        for child in node.body:
            if self.get_metadata(type(self), child, False):
                self.set_metadata(node, True)
                return
        self.set_metadata(node, False)

    def leave_If(self, node: cst.If) -> None:
        if node.orelse is None:
            self.set_metadata(node, False)
        else:
            self.set_metadata(node,
                self.get_metadata(type(self), node.body, False)
                and self.get_metadata(type(self), node.orelse, False))

    def leave_Else(self, node: cst.Else) -> None:
        self.set_metadata(node, self.get_metadata(type(self), node.body, False))



#([gaurds], expr])
_GAURDED_EXPR = tp.Tuple[tp.Sequence[cst.BaseExpression], cst.BaseExpression]

def _simplify_gaurds(
        gaurded_seq: tp.Sequence[_GAURDED_EXPR],
        ) -> tp.Sequence[_GAURDED_EXPR]:
    '''
    Pretty simplistic simplifyication
    which looks for:
        [
            ...,
            ([p, q], expri),
            ([p, not q], exprj),
            ...
        ]
    and simplifies it to:
        [
            ...,
            ([p, q], expri),
            ([p], exprj),
            ...
        ]
    also truncates the list after empty gaurds:
        [
            ...,
            ([], expr),
            ...
        ]
    becomes:
        [
            ...,
            ([], expr)
        ]
    '''
    # wrap the implementation so we can assert that 
    # we reach a fixed point after a single invocation
    def impl(gaurded_seq):
        new_seq = [gaurded_seq[0]]
        for gaurd, expr in gaurded_seq[1:]:
            last_gaurd = new_seq[-1][0]
            # Truncate
            if not last_gaurd:
                break
            elif not gaurd:
                new_seq.append((gaurd, expr))
                break

            pred = gaurd[-1]
            if (isinstance(pred, cst.UnaryOperation)
                and isinstance(pred.operator, cst.Not)
                and pred.expression == last_gaurd[-1]
                and gaurd[:-1] == last_gaurd[:-1]):
                # simplify
                new_seq.append((gaurd[:-1], expr))
            else:
                new_seq.append((gaurd, expr))
        return new_seq

    new_seq = impl(gaurded_seq)
    assert new_seq == impl(new_seq)
    return new_seq


class IncompleteGaurdError(Exception): pass

def _fold_conditions(
        gaurded_seq: tp.Sequence[_GAURDED_EXPR]
        ) -> cst.BaseExpression:
    def and_builder(
            left: cst.BaseExpression,
            right: cst.BaseExpression
            ) -> cst.BooleanOperation:
        return cst.BooleanOperation(
                left=left,
                operator=cst.And(),
                right=right,
        )

    if not gaurded_seq:
        raise IncompleteGaurdError()

    gaurd, expr = gaurded_seq[0]
    if not gaurd:
        return expr
    else:
        if len(gaurd) == 1:
            test = gaurd[0]
        else:
            test = ft.reduce(and_builder, gaurd)

        conditional = cst.IfExp(
                test=test,
                body=expr,
                orelse=_fold_conditions(gaurded_seq[1:])
            )
        return conditional

class NameTests(InsertStatementsVisitor):
    '''
    Rewrites if statements so that their tests are a single name
    This gaurentees that the conditions are ssa
    e.g:
        if x == 0:
            ...
        else:
            ...
    becomes:
        cond = x == 0
        if cond:
            ...
        else:
            ...
    '''
    format: str
    counter: int

    def __init__(self, prefix):
        super().__init__(cst.codemod.CodemodContext())
        self.format = prefix+'{}'
        self.counter = 0

    def leave_If(self,
            original_node: cst.If,
            updated_node: cst.If,
            ) -> cst.If:
        c_name = cst.Name(value=self.format.format(self.counter))
        self.counter += 1
        assign = cst.SimpleStatementLine([
            cst.Assign(
                targets=[cst.AssignTarget(c_name)],
                value=updated_node.test
            )
        ])
        self.insert_statements_before_current([assign])
        final_node = updated_node.with_changes(test=c_name)
        return super().leave_If(original_node, final_node)

class SingleReturn(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (ConditionProvider,)

    env: tp.Mapping[str, tp.Any]
    scope: tp.Optional[cst.FunctionDef]
    return_format: tp.Optional[str]
    returns: tp.MutableSequence[_GAURDED_EXPR]

    def __init__(self, env: tp.Mapping[str, tp.Any]):
        self.env = env
        self.scope = None
        self.return_format = None
        self.returns = []

    def visit_FunctionDef(self,
            node: cst.FunctionDef) -> tp.Optional[bool]:
        # prevent recursion into inner functions
        super().visit_FunctionDef(node)
        if self.scope is None:
            self.scope = node
            prefix = gen_free_prefix(node, self.env, '__return_value')
            self.return_format = prefix + '{}' 
            return True
        return False

    def leave_FunctionDef(self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef
            ) -> cst.FunctionDef:
        updated_node.validate_types_deep()
        if original_node is self.scope and self.returns:
            suite = updated_node.body
            try:
                return_val = _fold_conditions(_simplify_gaurds(self.returns))
            except IncompleteGaurdError:
                raise SyntaxError('Cannot prove function always returns') from None
            
            return_stmt = cst.SimpleStatementLine([cst.Return(value=return_val)])
            suite = suite.with_changes(body=(*suite.body, return_stmt))
            final_node = updated_node.with_changes(body=suite)
        else:
            final_node = updated_node

        return super().leave_FunctionDef(original_node, final_node)

    def visit_ClassDef(self,
            node: cst.ClassDef) -> tp.Optional[bool]:
        super().visit_ClassDef(node)
        return False

    def leave_Return(self,
            original_node: cst.Return,
            updated_node: cst.Return
            ) -> cst.Assign:
        assert self.return_format is not None
        r_name = cst.Name(value=self.return_format.format(len(self.returns)))
        cond = self.get_metadata(ConditionProvider, original_node)
        self.returns.append((cond, r_name))

        if updated_node.value is None:
            r_val = cst.Name(value='None')
        else:
            r_val = updated_node.value

        final_node = cst.Assign(
            targets=[cst.AssignTarget(r_name)],
            value=r_val,
        )
        return super().leave_Return(original_node, final_node)

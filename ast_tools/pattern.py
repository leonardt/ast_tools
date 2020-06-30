import re
import ast
import itertools


class NodePattern:
    """An individual node match, e.g. {x:Name}"""
    def __init__(self, s):
        self._parse(s)

    def _parse(self, s):
        """
        Extracts the name and type of the desired AST node.
        If no type is provided, then self.type is None.

        Type names are evaluated in a context with the ast module imported.
        """
        parts = tuple(s[1:-1].split(':'))
        self.name = parts[0]
        if len(parts) == 1:
            self.type = None
        else:
            assert (len(parts) == 2)
            self.type = getattr(ast, parts[1])


class ASTPattern:
    """
    A pattern for an AST subtree.

    Patterns are normal Python programs but with pieces replaced by NodePatterns.
    For example, to match a copy statement (x = y) looks like:

    {lhs:Name} = {rhs:Name}
    """
    def __init__(self, s):
        self.template = self._parse(s)

    def _parse(self, s):
        """
        Replace each node pattern with a unique variable name.
        """
        hole_id = 0
        self.var_map = {}

        def replace_incr(exp):
            nonlocal hole_id
            hole_id += 1
            name = '__hole{}'.format(hole_id)
            self.var_map[name] = NodePattern(exp.group(0))
            return name

        return ast.parse(re.sub(r'{[^}]*}', replace_incr, s)).body[0]

    def _match(self, pattern_node, actual_node):
        # If pattern_node is a lone variable (Expr of Name, or plain Name)
        # then extract the variable name
        if isinstance(pattern_node, ast.Name):
            pattern_var = pattern_node.id
        elif isinstance(pattern_node, ast.Expr) and \
             isinstance(pattern_node.value, ast.Name):
            pattern_var = pattern_node.value.id
        else:
            pattern_var = None

        # Check if pattern variable name corresponds to a hole in var_map
        if pattern_var is not None and pattern_var in self.var_map:
            node_pattern = self.var_map[pattern_var]

            # If the pattern variable type matches the actual node AST type,
            # then save the match and return True
            if node_pattern.type is None or \
               isinstance(actual_node, node_pattern.type):
                self._matches[node_pattern.name] = actual_node
                return True
            return False

        # Structural AST equality, adapted from
        # https://stackoverflow.com/questions/3312989/elegant-way-to-test-python-asts-for-equality-not-reference-or-object-identity
        if type(pattern_node) is not type(actual_node):
            return False
        if isinstance(pattern_node, ast.AST):
            for k, v in vars(pattern_node).items():
                if k in ('lineno', 'col_offset', 'end_lineno', 'end_col_offset', 'ctx', '_pp'):
                    continue
                if not self._match(v, getattr(actual_node, k)):
                    return False
            return True
        elif isinstance(pattern_node, list):
            return all(itertools.starmap(self._match, zip(pattern_node, actual_node)))
        return pattern_node == actual_node

    def match(self, node):
        self._matches = {}
        if self._match(self.template, node):
            return self._matches.copy()
        return None


def ast_match(pattern, node):
    return ASTPattern(pattern).match(node)

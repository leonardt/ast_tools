import ast
import code
import typing as tp
import warnings

import astor

import libcst as cst

from . import Pass
from . import PASS_ARGS_T
from ast_tools import to_module
from ast_tools.stack import SymbolTable

__ALL__ = ['debug']

class debug(Pass):
    def __init__(self,
            dump_ast: bool = False,
            dump_src: bool = False,
            dump_env: bool = False,
            file: tp.Optional[str] = None,
            append: tp.Optional[bool] = None,
            dump_source_filename: bool = False,
            dump_source_lines: bool = False,
            interactive: bool = False,
            ) -> PASS_ARGS_T:
        self.dump_ast = dump_ast
        self.dump_src = dump_src
        self.dump_env = dump_env
        if append is not None and file is None:
            warnings.warn('Option append has no effect when file is None', stacklevel=2)
        self.file = file
        self.append = append
        self.dump_source_filename = dump_source_filename
        self.dump_source_lines = dump_source_lines
        self.interactive = interactive

    def rewrite(self,
            tree: cst.CSTNode,
            env: SymbolTable,
            metadata: tp.MutableMapping) -> PASS_ARGS_T:

        def _do_dumps(dumps, dump_writer):
            for dump in dumps:
                dump_writer(f'BEGIN {dump[0]}\n')
                dump_writer(dump[1].strip())
                dump_writer(f'\nEND {dump[0]}\n\n')

        dumps = []
        if self.dump_ast:
            dumps.append(('AST', repr(tree)))
        if self.dump_src:
            dumps.append(('SRC', to_module(tree).code))
        if self.dump_env:
            dumps.append(('ENV', repr(env)))
        if self.dump_source_filename:
            if "source_filename" not in metadata:
                raise Exception("Cannot dump source filename without "
                                "apply_passes(..., debug=True)")
            dumps.append(('SOURCE_FILENAME', metadata["source_filename"]))
        if self.dump_source_lines:
            if "source_lines" not in metadata:
                raise Exception("Cannot dump source lines without "
                                "apply_passes(..., debug=True)")
            lines, start_line_number = metadata["source_lines"]
            dump_str = "".join(f"{start_line_number + i}:{line}" for i, line in
                               enumerate(lines))
            dumps.append(('SOURCE_LINES', dump_str))

        if self.file is not None:
            if self.append:
                mode = 'wa'
            else:
                mode = 'w'
            with open(self.dump_file, mode) as fp:
                _do_dumps(dumps, fp.write)
        else:
            def _print(*args, **kwargs): print(*args, end='', **kwargs)
            _do_dumps(dumps, _print)

        if self.interactive:
            # Launch a repl loop
            code.interact(
                banner=('Warning: modifications to tree, env, and metadata '
                        'will have side effects'),
                local=dict(tree=tree, env=env, metadata=metadata),
            )

        return tree, env, metadata

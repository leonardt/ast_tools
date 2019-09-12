import sys

from ast_tools.importer import RewriteImporter
from ast_tools.importer import module_passes
from ast_tools.passes import InstrumentationPass
from ast_tools.passes.instrumentation import INFO

_active = False
def activate():
    global _active
    if not _active:
        _active = True
        sys.meta_path.insert(0, RewriteImporter)
        module_passes.append(InstrumentationPass())

def deactivate():
    global _active
    if _active:
        _active = False
        new_meta_path = [i for i in sys.meta_path if i is not RewriteImporter]
        assert len(new_meta_path) == len(sys.meta_path) - 1
        sys.meta_path[:] = new_meta_path

        new_passes = [p for p in module_passes if not isinstance(p, InstrumentationPass)]
        assert len(new_passes) == len(module_passes) - 1
        module_passes[:] = new_passes

def clean_up():
    INFO.clear()



'''
setup script for package
'''

from setuptools import setup
from setuptools.command.build_py import build_py
from os import path
import util.generate_ast.generate as generate


PACKAGE_NAME = 'ast_tools'

with open('README.md', "r") as fh:
    LONG_DESCRIPTION = fh.read()

class BuildImmutableAst(build_py):
    def run(self):
        super().run()
        if not self.dry_run:
            src = generate.generate_immutable_ast()
            with open(path.join(PACKAGE_NAME, 'immutable_ast.py'), 'w') as f:
                f.write(src)

setup(
    cmdclass={'build_py' : BuildImmutableAst},
    name='ast_tools',
    url='https://github.com/leonardt/ast_tools',
    author='Leonard Truong',
    author_email='lenny@cs.stanford.edu',
    version='0.0.5',
    description='Toolbox for working with the Python AST',
    scripts=[],
    packages=[
        f"{PACKAGE_NAME}",
        f"{PACKAGE_NAME}.visitors",
        f"{PACKAGE_NAME}.transformers",
        f"{PACKAGE_NAME}.passes"
    ],
    install_requires=['astor'],
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown'
)

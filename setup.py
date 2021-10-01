'''
setup script for package
'''

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
from os import path
import util.generate_ast.generate as generate

PACKAGE_NAME = 'ast_tools'

with open('README.md', "r") as fh:
    LONG_DESCRIPTION = fh.read()

class Install(build_py):
    def run(self, *args, **kwargs):
        self.generated_outputs = []
        if not self.dry_run:
            src = generate.generate_immutable_ast()
            output_dir = path.join(self.build_lib, PACKAGE_NAME)
            self.mkpath(output_dir)
            output_file =  path.join(output_dir, 'immutable_ast.py')
            self.announce(f'generating {output_file}', 2)
            with open(output_file, 'w') as f:
                f.write(src)
            self.generated_outputs.append(output_file)
        super().run(*args, **kwargs)

    def get_outputs(self, *args, **kwargs):
        outputs = super().get_outputs(*args, **kwargs)
        outputs.extend(self.generated_outputs)
        return outputs


class Develop(develop):
    def run(self, *args, **kwargs):
        if not self.dry_run:
            src = generate.generate_immutable_ast()
            output_file =  path.join(PACKAGE_NAME, 'immutable_ast.py')
            self.announce(f'generating {output_file}', 2)
            with open(output_file, 'w') as f:
                f.write(src)
        super().run(*args, **kwargs)

setup(
    cmdclass={
        'build_py': Install,
        'develop': Develop,
        },
    name='ast_tools',
    url='https://github.com/leonardt/ast_tools',
    author='Leonard Truong',
    author_email='lenny@cs.stanford.edu',
    version='0.1.8',
    description='Toolbox for working with the Python AST',
    scripts=[],
    packages=[
        f'{PACKAGE_NAME}',
        f'{PACKAGE_NAME}.cst_utils',
        f'{PACKAGE_NAME}.metadata',
        f'{PACKAGE_NAME}.passes',
        f'{PACKAGE_NAME}.transformers',
        f'{PACKAGE_NAME}.visitors',
    ],
    install_requires=[
        'astor',
        'libcst',
    ],
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown'
)

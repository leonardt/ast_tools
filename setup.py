"""
setup script for package
"""

from setuptools import setup

with open("README.md", "r") as fh:
    LONG_DESCRIPTION = fh.read()

setup(
    name='ast_tools',
    url='https://github.com/leonardt/ast_tools',
    author='Leonard Truong',
    author_email='lenny@cs.stanford.edu',
    version='0.0.2',
    description='Toolbox for working with the Python AST',
    scripts=[],
    packages=[],
    install_requires=['astor'],
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown"
)

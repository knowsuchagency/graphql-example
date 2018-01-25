#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""
from setuptools import setup

try:
    import pipenv
except ImportError:
    print('pipenv not installed for current python')
    print('using vendored version in ./vendor/')
    import sys

    sys.path.append('vendor')
finally:
    from pipenv.project import Project
    from pipenv.utils import convert_deps_to_pip

# get requirements from Pipfile
pfile = Project(chdir=False).parsed_pipfile
default = convert_deps_to_pip(pfile['packages'], r=False)
development = convert_deps_to_pip(pfile['dev-packages'], r=False)

# extract dependency links
dependency_links = []

for dependencies in (default, development):
    for index, dependency in enumerate(dependencies):
        if '+' in dependency:
            *_, dependency_link = dependency.split()
            dependency_links.append(
                dependency_link
            )
            dependencies.pop(index)

setup(
    install_requires=default,
    tests_require=development,
    dependency_links=dependency_links,
    extras_require={
        'dev': development,
        'development': development,
        'test': development,
        'testing': development,
    },

    entry_points={
        'console_scripts': [
            'graphql_example=graphql_example.cli:main'
        ]
    },

)

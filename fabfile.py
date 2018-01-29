from functools import singledispatch
from pathlib import Path

import pkg_resources

from fabric.api import *

import nbformat
import nbconvert

@task
def slideshow():
    local('jupyter nbconvert '
          'graphql_example/graphql_example.ipynb '
          '--to slides --post serve')


def overwrite_module_from_notebook():
    """Overwrite graphql_example.py from same-named notebook"""

    nbfilename = pkg_resources.resource_filename('graphql_example',
                                                 'graphql_example.ipynb')

    notebook = nbformat.read(nbfilename, as_version=4)

    exporter = nbconvert.PythonExporter()

    body, *_ = exporter.from_notebook_node(notebook)

    module_filename = pkg_resources.resource_filename('graphql_example',
                                                      'graphql_example.py')

    with open(module_filename, 'w') as main_module:
        main_module.write(body)


@task
def clean_build():
    """Remove build artifacts."""
    local('rm -fr build/')
    local('rm -fr dist/')
    local('rm -rf .eggs/')
    local("find . -name '*.egg-info' -exec rm -fr {} +")
    local("find . -name '*.egg' -exec rm -f {} +")


@task
def clean_pyc():
    """Remove Python file artifacts."""
    local("find . -name '*.pyc' -exec rm -f {} +")
    local("find . -name '*.pyo' -exec rm -f {} +")
    local("find . -name '*~' -exec rm -f {} +")
    local("find . -name '__pycache__' -exec rm -fr {} +")


@task
def clean_test():
    """Remove test and coverage artifacts."""
    local('rm -fr .tox/')
    local('rm -f .coverage')
    local('rm -fr htmlcov/')


@task
def clean():
    """Remove all build, test, coverage and Python artifacts."""
    clean_build()
    clean_pyc()
    clean_test()


@task
def test(capture=True, pdb=False):
    """
    Run tests quickly with default Python.

    Args:
        capture: capture stdout [default: True]
    """
    prepare_files()
    flags = ' '.join(
        ['-s' if not true(capture) else '',
         '--pdb' if true(pdb) else ''])
    local('py.test tests/ ' + flags)


@task(alias='tox')
def test_all(absolute_path=None):
    """Run on multiple Python versions with tox."""
    local('tox')


@task
def coverage(open_browser=True):
    """Check code coverage quickly with the default Python."""
    local('coverage run --source graphql_example -m pytest')
    local('coverage report -m')
    local('coverage html')
    if true(open_browser):
        local('open htmlcov/index.html')


@task
def dist():
    """Build source and wheel package."""
    clean()
    local('python setup.py sdist')
    local('python setup.py bdist_wheel')


@task
def release():
    """Package and upload a release to pypi."""
    clean()
    test()
    local('python setup.py sdist bdist_wheel')
    local('twine upload dist/*')


@task
def prepare_readme():
    """Convert notebook to markdown and write it to the readme."""
    from nbconvert import MarkdownExporter
    import nbformat

    print('reading notebook')
    notebook = nbformat.reads(
        Path('graphql_example/graphql_example.ipynb').read_text(),
        as_version=4)

    print('converting notebook to RST')
    exporter = MarkdownExporter()
    body, *_ = exporter.from_notebook_node(notebook)

    print('writing to RST to readme')
    with open('README.md', 'w') as readme:
        readme.write(body)

    print('success')


@task
def prepare_module():
    """Replace graphql_example module with notebook."""
    overwrite_module_from_notebook()


@task
def prepare_files():
    """Programmatically update both modules and readme."""
    prepare_module()
    prepare_readme()


@task
def publish_to_github():
    """Prepare readme and modules."""
    prepare_files
    local('git push')


@task
def runserver(
    port='8080',
    host='localhost',
):
    prepare_files()
    local(f'graphql_example runserver '
          f'--host {host} --port {port}')


@singledispatch
def true(arg):
    """
    Determine of the argument is True.

    Since arguments coming from the command line
    will always be interpreted as strings by fabric
    this helper function just helps us to do what is
    expected when arguments are passed to functions
    explicitly in code vs from user input.

    Just make sure NOT to do the following with task arguments:

    @task
    def foo(arg):
        if arg: ...

    Always wrap the conditional as so

    @task
    def foo(arg):
        if true(arg): ...

    and be aware that true('false') -> False

    Args:
        arg: anything

    Returns: bool

    """
    return bool(arg)

@true.register(str)
def _(arg):
    """If the lowercase string is 't' or 'true', return True else False."""
    argument = arg.lower().strip()
    return argument == 'true' or argument == 't'

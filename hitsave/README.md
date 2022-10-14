# hitsave

Holistic caching for python.

# Quickstart

In your project:

```sh
cd ~
git clone git@github.com:EdAyers/hitsave.git
cd ~/my_project
pip install -e ~/hitsave
```

Take any functon in your project, decorate it with `@save`:
You can also run the `test_save.py` file to witness this.

```py
from hitsave import save

def dependency(y):
  # try changing the method body!
  return y + y

@save
def long_running_function(x):
  print f"Running {x}!"
  return x + 2 + dependency(x)

long_running_function(3)
long_running_function(4)
```

When you run this python file, `@save` will cache the results to disk (and to our cloud service).
When you run the file again, the cache will be used rather than re-running the function.
`@save` analyses the code-dependencies of your code and determines when to invalidate the cache.
You can add `@save` to any function where the output is picklable.

# Usage

## CLI

`hitsave` has a CLI. You can use this to:
- query your data caches
- log-in to hitsave Cloud.

## Package

- All logs use the `"hitsave"` logger. To view detailed logs [todo]

# Development

## How to have a python installation that doesn't make you hate everything

- Install `pyenv`. On mac it's easy but I remember it being a faff to get it set up on arch.
- `pyenv install 3.10.6`
- Typing `python --version` in this directory should give `3.10.6`
- `python -m venv .env` creates a new python 'virtual environment', this means you can install packages without breaking everything.
- To activate the shell to use the environment do `source .env/bin/activate`.
- If you open this directory in vscode with the python extension, it should ask you to use `.env` as the environment and then it will automatically enter the environment in all the shells etc.
- `pip install -r requirements.txt` installs the packages. `pip install -r dev_requirements.txt` installs the developer reqs (pytest etc).
- `pip install -e .` installs the `hitsave` package.

## tests

- run the tests with `pytest`
- run the linter with `black .`


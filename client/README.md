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

Take any functon in your project, decorate it with `@memo`: You can also run the
`test_save.py` file to witness this.

```py
from hitsave import memo

def dependency(y):
  # try changing the method body!
  return y + y

@memo
def long_running_function(x):
  print f"Running {x}!"
  return x + 2 + dependency(x)

long_running_function(3)
long_running_function(4)
```

When you run this python file, `@memo` will cache the results to disk (and to
our cloud service). When you run the file again, the cache will be used rather
than re-running the function. `@memo` analyses the code-dependencies of your
code and determines when to invalidate the cache. You can add `@memo` to any
function where the output is picklable.

# Usage

## CLI

`hitsave` has a CLI. You can use this to:

- query your data caches
- log-in to hitsave Cloud.

## Package

- All logs use the `"hitsave"` logger. To view detailed logs [todo]

# Development

## How to have a python installation that doesn't make you hate everything

- Install `pyenv`. On mac it's easy but I remember it being a faff to get it set
  up on arch.
- `pyenv install 3.10.6`. [todo] some caveats here, make sure you have some
  dlls: `readline`, `zlib`, possibly sqlite, openssl?
- Typing `python --version` in this directory should give `3.10.6`
- `python -m venv .env` creates a new python 'virtual environment', this means
  you can install packages without breaking everything.
- To activate the shell to use the environment do `source .env/bin/activate`.
- If you open this directory in vscode with the python extension, it should ask
  you to use `.env` as the environment and then it will automatically enter the
  environment in all the shells etc.
- `pip install -e .` installs the `hitsave` package. If you get
  `ERROR: File "setup.py" or "setup.cfg" not found.`, you should upgrade pip
  with `pip install --upgrade pip`.
- to install extra deps do `pip install -r dev_requirements.txt`. This is
  currently a grab-bag of everything you might possibly need and should be
  tidied up and incorporated in to pyproject.toml before release.

## Other versions of python

- `pyenv install 3.8.14`
- `pyenv local 3.8.14`
- `python -m venv env/8`
- `source env/8/bin/activate`

## tests

- run the tests with `pytest`
- run the linter with `black .`

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
- run the docgen with `cd docs`; `make html`

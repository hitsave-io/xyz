# Installation

### Installation with PyPI (recommended)

[todo] submit to pypi

```sh
pip install hitsave
```

### Installation from source

```sh
cd $MY_PROJECTS
git clone git@github.com:hitsave-io/hitsave.git
```

Then, you can install HitSave using pip.

```sh
pip install -e $MY_PROJECTS/hitsave
```

## Creating an API key

You can use HitSave API keys to authorise your computer

To generate an API key from your terminal, use

```sh
hitsave keygen
```

It will then prompt you to sign in with github, generate an API key and then
offer to place the key in your zshenv file.

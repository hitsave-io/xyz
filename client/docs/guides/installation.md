# Installation

## Installation from PyPI

To install HitSave in your project, run

```sh
$ pip install hitsave
```

You can import the core HitSave decorators, [`@memo`](hitsave.memo) and
[`@experiment`](hitsave.experiment). HitSave also provides a CLI tool
for managing your environment.

(create_account)=

## Create a HitSave account

In order to use cloud caching and experiment management, create a
HitSave account by signing in with GitHub. Run

```teminal
$ hitsave login
```

and a browser window will open allowing you to login via GitHub. Once
done, you will be directed back to the terminal.

## Creating an API key

The HitSave Python client authenticates with the cloud server using an
API key. You can generate as many API keys as you need (e.g. one for
each machine using HitSave).

API keys should be kept very secret, as they allow anyone to
authenticate as you. Please ensure you don't share API keys or check
them into your source code repository.

To generate an API key from your terminal, run

```sh
$ hitsave keygen
```

If you are not already logged in, you will be prompted to do so first,
as described [above](create_account).

Once the key has been generated, the HitSave CLI will save it to your
config file (usually located somewhere like `~/.config/hitsave`). You
should now be able to run Python code which includes functions decorated
with the HitSave decorators, and have the cache sync automatically to
the cloud.

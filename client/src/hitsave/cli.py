from typing import Dict, Optional
import typer
import asyncio
import platform
from aiohttp import web
import json
import uuid
import logging
import urllib.parse
import aiohttp
import os
from hitsave.authenticate import (
    AuthenticationError,
    generate_api_key,
    get_jwt,
    loopback_login,
)
from hitsave.config import Config
from hitsave.evalstore import EvalStore
from hitsave.session import Session
from hitsave.util import decorate_ansi, decorate_url, eprint, is_interactive_terminal

app = typer.Typer()
""" Entrypoint for CLI tool. """

logger = logging.getLogger("hitsave")
# logger.setLevel(logging.DEBUG)


@app.command()
def serve():
    """Runs the hitsave LSP server."""
    from hitsave.server import main

    main()


@app.command()
def login():
    """Log in or sign up to the HitSave cloud service.

    This will present a link to you which can be used to register hitsave using your github account."""
    asyncio.run(loopback_login())


async def keygen_async():
    """Interactive workflow for generating a new api key."""
    if Config.current().api_key is not None:
        eprint("Warning: an API key for hitsave is already present.")
        if is_interactive_terminal():
            eprint(
                "Please press enter to confirm that you wish to generate another API key."
            )
            input(">")
    label = platform.node()

    async def login():
        if is_interactive_terminal():
            await loopback_login()
        else:
            raise AuthenticationError(
                "Please login by running `hitsave login` in an interactive terminal."
            )

    if get_jwt() is None:
        await login()
    try:
        api_key = await generate_api_key(label)
    except AuthenticationError as err:
        eprint("Authentication session expired, please log in again:")
        await login()
        api_key = await generate_api_key(label)

    if not is_interactive_terminal():
        # if a human is not viewing the terminal, it should just print
        # api_key on stdout and exit.
        print(api_key)
        return
    eprint(
        "API keys are used to provide programmatic access to the HitSave cloud API.\n",
        "This API key should be stored in a secret location and not shared, as anybody\ncan use it to authenticate as you.",
        "To revoke an API key, visit ",
        decorate_url("https://hitsave.io/my-keys"),
        # "Otherwise, [see here]() for other ways to load your API key into the HitSave client.",
        "\n\n",
        decorate_ansi(api_key, bold=True, fg="green"),
        "\n",
        sep="",
    )
    shells = {
        "/bin/zsh": "~/.zshenv",
        "/bin/bash": os.environ.get("BASH_ENV"),
    }
    sh = os.environ.get("SHELL", "??")
    envfile = shells[sh]
    if envfile is not None:
        cmd = f"export HITSAVE_API_KEY={api_key}"
        # [todo] what if an api key var is already present?
        eprint(
            decorate_ansi(f"Enter 'y' to append the following to {envfile}:"),
            "\n\n",
            decorate_ansi(cmd, fg="white"),
            "\n",
            sep="",
        )
        i = input(">")
        if i == "y":
            with open(os.path.expanduser(envfile), "at") as fd:
                fd.writelines([cmd])
            # [todo] there is a way of doing this without needing a restart iirc
            eprint("Successful, reload the terminal to start using hitsave.")
            return
    doc_url = decorate_url("https://hitsave.io/doc/keys")
    eprint(
        f"Please see {doc_url} for ways you can include this key in your environment."
    )


@app.command()
def keygen(label: Optional[str] = None):
    """Generate a fresh API key.

    If the current shell is zsh, you will also be asked whether you
    want to append the API key to your .zshenv file.
    """
    asyncio.run(keygen_async())


@app.command()
def clear_local():
    """Deletes the local eval store (not cached blobs)."""
    store = EvalStore().local
    p = Config.current().local_db_path
    eprint(f"Deleting {len(store)} entries in {p}")
    store.clear()


"""
[todo] clear cloud cache
[todo] snapshot a directory, upload it and return the digest.
[todo] snapshot a file
 """

if __name__ == "__main__":
    app()

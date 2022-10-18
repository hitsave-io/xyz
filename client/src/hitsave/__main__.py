from typing import Dict
import typer
import asyncio
import platform
from aiohttp import web
import json
import uuid
import urllib.parse
import aiohttp
import os
from hitsave.authenticate import AuthenticationError, generate_api_key, get_jwt, loopback_login
from hitsave.config import cloud_api_key, cloud_url
from hitsave.util import eprint, is_interactive_terminal

app = typer.Typer()


@app.command()
def serve():
    from hitsave.server import main

    main()

@app.command()
def login():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(loopback_login())

async def keygen_async():
    """ Interactive workflow for generating a new api key.  """
    if cloud_api_key is not None:
        eprint('Warning: an API key for hitsave is already present. ')
    label = platform.node()
    async def login():
        if is_interactive_terminal():
            await loopback_login()
        else:
            raise AuthenticationError("Please login by running `hitsave login` in an interactive terminal.")

    if get_jwt() is None:
        await login()
    try:
        api_key = await generate_api_key(label)
    except AuthenticationError as err:
        eprint("Authentication session expired, please log in again:")
        await login()
        api_key = await generate_api_key(label)

    if not is_interactive_terminal():
        print(api_key)
        return
    eprint(
        "API keys are used to provide programmatic access to the HitSave cloud API.\n",
        "This API key should be stored in a secret location and not shared, as anybody\ncan use it to authenticate as you.",
        "To revoke an API key, visit https://hitsave.io/my-keys\n",
        # "Otherwise, [see here]() for other ways to load your API key into the HitSave client.",
        "\n\n",
        api_key, "\n\n",
    )
    shells = {
        '/bin/zsh' : '~/.zshenv',
        '/bin/bash' : os.environ.get('BASH_ENV'),
    }
    sh = os.environ.get('SHELL', "??")
    envfile = shells[sh]
    if envfile is not None:
        cmd = f"export HITSAVE_API_KEY={api_key}"
        eprint(f"Type 'y' to append the following to {envfile}:\n{cmd}")
        i = input('>')
        if i == "y":
            with open(envfile, 'wa') as fd:
                fd.writelines([cmd])
            # [todo] there is a way of doing this without needing a restart iirc
            eprint("Successful, reload the terminal to start using hitsave.")
            return

    eprint("Please see https://hitsave.io/doc/keys for how to include the key in your environment.")

@app.command()
def keygen():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(keygen_async())

if __name__ == "__main__":
    app()

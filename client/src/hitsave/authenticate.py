import asyncio
import json
import logging
import os.path
from typing import Dict, Optional
import webbrowser
from aiohttp import web
import aiohttp
from hitsave.config import Config
from hitsave.util import (
    decorate_ansi,
    decorate_url,
    eprint,
    hyperlink,
    is_interactive_terminal,
)

import urllib.parse
import uuid

""" Code for connecting to auth server.

[todo] consider removing async code, there is nothing that needs to be concurrent here.
"""

logger = logging.getLogger("hitsave")
# [todo], not a huge security hole, but this should really be stored with care,
# since anyone who gets access to it can pretend to be the user.
# I think the answer is to place it in a designated config directory.


def jwt_path():
    return os.path.join(Config.current().local_cache_dir, "hitsave-session.jwt")


class AuthenticationError(RuntimeError):
    pass


def save_jwt(jwt: str):
    p = jwt_path()
    if os.path.exists(p):
        logger.debug(f"File {p} already exists, overwriting.")
    else:
        logger.debug(f"Writing authentication JWT to {p}.")
    with open(p, "wt") as file:
        file.write(jwt)


def get_jwt() -> Optional[str]:
    """Gets the cached JWT. If it doesn't exist, returns none."""
    p = jwt_path()
    if not os.path.exists(p):
        logger.debug(f"File {p} does not exist.")
        return None
    with open(p, "rt") as file:
        logger.debug(f"Reading JWT from {p}.")
        return file.read()


async def loopback_login():
    """Interactive workflow to perform the github authentication loop.

    ① present a sign-in-with-github link to the user in the terminal
    ② ping api.hitsave.io/user/login for a new JWT
    ③ return the JWT and store it locally the JWT in a local file

    A holder of this JWT, for the period that it is valid, is authenticated in hitsave as the person
    who logged in.
    """

    if not is_interactive_terminal():
        raise RuntimeError(
            "Can't authenticate the user in a non-interactive terminal session."
        )

    # [todo] if there is already a valid jwt, don't bother logging in here.
    # attempt to use the jwt for something, if there is an error (401) then you prompt a login.
    cloud_url = Config.current().cloud_url
    redirect_port = 9449  # [todo] check not claimed.
    miniserver_url = urllib.parse.quote(f"http://127.0.0.1:{redirect_port}")
    query_params = {
        "client_id": "b7d5bad7787df04921e7",
        "redirect_uri": f"http://127.0.0.1:3000/login?client_loopback={miniserver_url}",
        "scope": "user:email",
    }
    # query_params = urllib.parse.urlencode(query_params)
    query_params = "&".join(
        [f"{k}={q}" for k, q in query_params.items()]
    )  # [note] this gives slightly nicer messages.
    sign_in_url = f"https://github.com/login/oauth/authorize?{query_params}"
    # [todo] check user isn't already logged in

    fut = asyncio.get_running_loop().create_future()

    async def redirected(request: web.BaseRequest):
        """Handler for the mini webserver"""
        ps = dict(request.url.query)
        assert "jwt" in ps
        fut.set_result(ps)
        return web.Response(text="")

    # ref: https://docs.aiohttp.org/en/stable/web_lowlevel.html
    server = web.Server(redirected)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", redirect_port)
    await site.start()
    # [todo] https://docs.python.org/3/library/webbrowser.html
    decorated = decorate_ansi(sign_in_url, fg="blue")
    eprint("Opening", decorated)
    webbrowser.open_new(sign_in_url)

    result = await fut
    # [todo] are these stopper thingies needed?
    await site.stop()
    await runner.cleanup()
    await server.shutdown()
    assert "jwt" in result
    jwt = result["jwt"]
    save_jwt(jwt)
    eprint("Successfully logged in.")
    return jwt


async def generate_api_key(label: str):
    """Assuming that the user is authenticated (that is, a valid JWT is cached), this will
    ask the server to generate a new hitsave api key with the given label.
    """
    jwt = get_jwt()
    cloud_url = Config.current().cloud_url
    if jwt is None:
        raise AuthenticationError("User has not logged in.")

    logger.info(f"Asking {cloud_url} for a new API key with label {label}.")
    async with aiohttp.ClientSession(
        cloud_url, headers={"Authorization": f"Bearer {jwt}"}
    ) as session:
        async with session.get("/api_key/generate", params={"label": label}) as resp:
            if resp.status == 401:
                msg = await resp.text()
                logger.info(msg)
                raise AuthenticationError(f"Authentication session has expired.")
            resp.raise_for_status()
            if resp.content_type == "application/json":
                raise NotImplementedError(
                    "json response to /api_key/generate not implemented"
                )
            elif resp.content_type == "text/plain":
                api_key = await resp.text()
            else:
                raise Exception(f"Unknown content_type {resp.content_type}")
    logger.debug(f"Successfully recieved new API key")
    return api_key

import asyncio
import json
import logging
import os.path
from typing import Dict, Optional
from aiohttp import web
import aiohttp
from hitsave.config import tmp_dir, cloud_url, cloud_api_key
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
jwt_path = os.path.join(tmp_dir, "hitsave-session.jwt")


class AuthenticationError(RuntimeError):
    pass


def save_jwt(jwt: str):
    if os.path.exists(jwt_path):
        logger.debug(f"File {jwt_path} already exists, overwriting.")
    else:
        logger.debug(f"Writing authentication JWT to {jwt_path}.")
    with open(jwt_path, "wt") as file:
        file.write(jwt)


def get_jwt() -> Optional[str]:
    """Gets the cached JWT. If it doesn't exist, returns none."""
    if not os.path.exists(jwt_path):
        logger.debug(f"File {jwt_path} does not exist.")
        return None
    with open(jwt_path, "rt") as file:
        logger.debug(f"Reading JWT from {jwt_path}.")
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
    redirect_port = 9449  # [todo] check not claimed.
    query_params = {
        "client_id": "b7d5bad7787df04921e7",
        "redirect_uri": f"http://127.0.0.1:{redirect_port}",
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
        assert "code" in ps
        # [todo] what happens if multiple responses?
        fut.set_result(ps)
        """ [todo] this could be a fancy page:
        - the API key is shown in the browser window instead of in the terminal
        - you get a css-pretty page saying to return to the terminal
        - you get a redirect to the hitsave getting started page?
        - you return a page which calls `window.close()`?
        - figure out how to get terminal to regain focus
        """
        return web.Response(text="login successful, please return to your terminal")

    # ref: https://docs.aiohttp.org/en/stable/web_lowlevel.html
    server = web.Server(redirected)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", redirect_port)
    await site.start()
    decorated = decorate_url(href=sign_in_url, text=">> sign in with github <<")
    eprint("Please follow the link below to log in:", "\n\n", decorated, "\n", sep="")

    result = await fut
    # [todo] are these stopper thingies needed?
    await site.stop()
    await runner.cleanup()
    await server.shutdown()
    assert "code" in result
    login_params = {"code": result["code"]}
    # always create a different http session for logging in
    eprint(f'Connecting to {cloud_url}...')
    async with aiohttp.ClientSession(cloud_url) as session:
        async with session.post("/user/login", params=login_params) as resp:
            resp.raise_for_status()
            if resp.content_type == "application/json":
                j = await resp.json()
                assert "token" in j
                jwt = j["token"]
            elif resp.content_type == "text/plain":
                jwt = await resp.text()
            else:
                # [todo] is this the right exception?
                raise TypeError(
                    f"Unsupported response content type {resp.content_type}."
                )
    save_jwt(jwt)
    eprint("Successfully logged in.")
    return jwt


async def generate_api_key(label: str):
    """Assuming that the user is authenticated (that is, a valid JWT is cached), this will
    ask the server to generate a new hitsave api key with the given label.
    """
    jwt = get_jwt()
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

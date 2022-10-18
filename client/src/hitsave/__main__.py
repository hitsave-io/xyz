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
from hitsave.util import eprint

app = typer.Typer()


@app.command()
def serve():
    from hitsave.server import main

    main()


async def login_async():
    api_key = os.environ.get("HITSAVE_API_KEY", None)
    if api_key is not None:
        eprint(
            "Already logged in with an API key (HITSAVE_API_KEY). Please delete it from your environment to log in again."
        )

        # [todo] still log in?
    # [todo] if there is already a valid jwt, don't bother logging in here.
    # attempt to use the jwt for something, if there is an error (401) then you prompt a login.
    redirect_port = 9449  # [todo] check not claimed.
    query_params = {
        "state": uuid.uuid4().hex,
        "client_id": "b7d5bad7787df04921e7",
        "redirect_uri": f"http://127.0.0.1:{redirect_port}",
        "scope": "user:email",
    }
    sign_in_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(query_params)}"
    # [todo] check user isn't already logged in

    fut = asyncio.get_running_loop().create_future()

    async def redirected(request: web.BaseRequest):
        """Handler for the mini webserver"""
        ps = dict(request.url.query)
        assert ps["state"] == query_params["state"], "bad state"
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

    eprint(f"Sign in with github by following the link below:")
    eprint(sign_in_url)

    result = await fut
    print(f"got {result}")
    assert "code" in result
    login_params = { "code": result["code"] }

    # [todo] get from env.
    url = "http://localhost:8080"  # 'https://api.hitsave.io'

    async with aiohttp.ClientSession(url) as session:
        async with session.post("/user/login", params=login_params) as resp:
            resp.raise_for_status()
            assert resp.content_type == "text/plain"
            # result is a jwt
            # [todo] save this as local state somewhere.
            jwt = await resp.text()
        # [todo] make label the hostname
        # [todo] interactive prompt to get a label
        label = platform.node()
        eprint(f"Creating a new api key with label {label} ... ")
        async with session.get(
            "/api_key/generate",
            headers={"Authorization": f"Bearer {jwt}"},
            params={"label": label},
        ) as resp:
            resp.raise_for_status()
            assert resp.content_type == "text/plain"
            api_key = await resp.text()
        eprint(
            f"You are now logged in. We have generated an API key for this machine: \n\n",
            api_key, "\n\nPlease save this in your environment file.",
            "You can manage your api keys at https://hitsave.io/mykeys"
        )
        # [todo] save it for the user to best-guess envfile if they really want.

@app.command()
def login():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(login_async())


if __name__ == "__main__":
    app()

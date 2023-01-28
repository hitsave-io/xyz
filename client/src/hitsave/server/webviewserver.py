import asyncio
from dataclasses import dataclass
import os
import logging
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import ClientInfo
from hitsave.server.proxy_session import ProxySession
from hitsave.server.transport import Transport
import sys
import urllib.parse
import importlib
import importlib.util
from hitsave.decorator import SavedFunction
from hitsave.server.lsptypes import (
    CodeLensParams,
    Range,
)
from hitsave.session import Session
from hitsave.symbol import module_name_of_file
from hitsave.server.reactor import h, Reactor

logger = logging.getLogger("hitsave.webview-server")


def HelloWorld(props):
    sess: ProxySession = props.get("session")

    return [
        h("h1", {"style": {"color": "red"}}, "Hello world"),
        h("p", {}, "result:", str(sess.workspace_dir)),
    ]


class WebviewServer(RpcServer):
    def __init__(self, transport: Transport, proxy_session: ProxySession):
        super().__init__(transport=transport)
        self.proxy_session = proxy_session
        self.reactor = Reactor(spec=h(HelloWorld, {"session": self.proxy_session}))
        self.reactor.initialize()
        self.dispatcher.register("render")(self.render)
        self.patcher_loop_task = asyncio.create_task(self.patcher_loop())

    async def render(self, params):
        return self.reactor.render()

    async def patcher_loop(self):
        while True:
            patches = await self.reactor.get_patches()
            if len(patches) > 0:
                await self.notify("patch", patches)

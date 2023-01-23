from dataclasses import dataclass
import os
import logging
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import ClientInfo
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
    return h("h1", {"style": {"color": "red"}}, "Hello world")


class WebviewServer(RpcServer):
    def __init__(self, transport: Transport):
        super().__init__(transport=transport)
        self.reactor = Reactor(spec=h(HelloWorld, {}))
        self.dispatcher.register("initialize")(self.initialize)
        self.dispatcher.register("render")(self.render)

    async def render(self, params):
        return self.reactor.render()

    async def initialize(self, params):
        logger.debug(f"initialize: {params}")
        init_render = self.reactor.initialize()
        return init_render

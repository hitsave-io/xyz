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

logger = logging.getLogger("hitsave.webview-server")

DISPATCHER = Dispatcher()


def method(name=None):
    return DISPATCHER.register(name)


class WebviewServer(RpcServer):
    def __init__(self, transport: Transport):
        super().__init__(transport=transport, dispatcher=DISPATCHER)


@dataclass
class InitializeParams:
    clientInfo: ClientInfo


@method()
async def initialize(params: InitializeParams):
    logger.debug(f"Initialising webview server with {params}")

    return {}

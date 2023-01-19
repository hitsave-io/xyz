from asyncio import Future, StreamReader, StreamWriter, Task
import asyncio
from functools import singledispatch
from dataclasses import MISSING, asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, Union, Coroutine
import inspect
import logging
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.util.ofdict import MyJsonEncoder, ofdict
import json
from hitsave.server.transport import Transport

logger = logging.getLogger("hitsave.lsp")

LSP_DISPATCHER = Dispatcher()


def method(name=None):
    return LSP_DISPATCHER.register(name)


class LanguageServer(RpcServer):
    def __init__(self, transport: Transport):
        super().__init__(transport=transport, dispatcher=LSP_DISPATCHER)

import asyncio
from dataclasses import dataclass, field, replace
import os
import logging
from pathlib import Path
from typing import Any, Optional
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import ClientInfo, TextDocumentIdentifier
from hitsave.server.proxy_session import ProxySession, SavedFunctionInfo
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
from hitsave.symbol import Symbol, module_name_of_file
from hitsave.server.reactor import EventArgs, h, Manager, Html, useEffect, useState
from hitsave.console import console, logger
import hitsave.server.hsptypes as hsp


@dataclass
class AppProps:
    session: ProxySession
    file: Optional[TextDocumentIdentifier]
    focussed_symbol: Optional[Symbol] = field(default=None)


def SavedFunctionView(props: dict) -> Html:
    sfi: SavedFunctionInfo = props["info"]
    is_open = props["is_open"]
    n_deps = len(sfi.dependencies)
    return h(
        "details",
        {"open": is_open},
        [
            h("summary", {}, [sfi.name]),
            h("div", {}, [str(sfi.filepath), ":", str(sfi.line_start)]),
            h(
                "details",
                {},
                [
                    h("summary", {}, [f"Dependencies ({n_deps})"]),
                    "...",
                ],
            ),
            h(
                "details",
                {},
                [
                    h("summary", {}, [f"Timeline"]),
                    "...",
                ],
            ),
            h("details", {}, [h("summary", {}, ["Evaluations (###)"]), "..."]),
        ],
    )


def AppView(props: AppProps) -> Html:
    sess: ProxySession = props.session
    symb = props.focussed_symbol
    x: Any
    x, set_x = useState(None)
    logger.info(f"Rendering AppView with {props}")

    async def handle():
        if not props.file:
            return
        logger.info(f"Getting info for {props.file}")
        v: Any = await sess.get_info_for_file(props.file)
        logger.info(f"Got info for {props.file}")
        set_x(v)

    useEffect(handle, [props.file])

    if x is None:
        return "loading..."

    def mk_item(s: SavedFunctionInfo):
        is_open = hash(s.symbol) == hash(symb)
        return h(SavedFunctionView, dict(info=s, is_open=is_open))

    return [
        h("h2", {}, str(props.file)),
        h("p", {}, "result:", str(sess.workspace_dir)),
        [mk_item(y) for y in x],
    ]


class WebviewServer(RpcServer):
    initialized: bool
    reactor: Manager
    patcher_loop_task: asyncio.Task

    def __init__(self, transport: Transport):
        super().__init__(transport=transport)
        self.dispatcher.register("render")(self.render)
        self.dispatcher.register("event")(self.handle_event)
        self.dispatcher.register("initialize")(self.initialize)

    async def initialize(self, params: hsp.InitParams):
        assert params.workspace_dir is not None
        assert params.type == "webview"
        self.proxy_session = ProxySession.get(params.workspace_dir)
        self.state = AppProps(
            session=self.proxy_session, focussed_symbol=None, file=None
        )
        self.reactor = Manager()
        self.reactor.update(h(AppView, self.state))
        self.initialized = True
        logger.debug(f"{self} initialized")
        self.patcher_loop_task = asyncio.create_task(self.patcher_loop())
        return {}

    async def render(self, params):
        logger.debug(f"{self} rendering")
        assert self.initialized
        return self.reactor.render()

    async def handle_event(self, params: EventArgs):
        assert self.initialized
        return self.reactor.handle_event(params)

    async def patcher_loop(self):
        assert self.initialized
        while True:
            try:
                patches = await self.reactor.wait_patches()
                if len(patches) > 0:
                    result = await self.request(
                        "patch", []
                    )  # [todo] send encoded patches
                    logger.debug(f"patcher_loop: patched: {result}")
            except Exception as e:
                # [todo] this is for debugging only
                logger.error(e)
                console.print_exception()

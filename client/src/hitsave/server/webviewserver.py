import asyncio
from dataclasses import dataclass
import os
import logging
from typing import Any
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
from hitsave.server.reactor import EventArgs, h, Reactor, Spec, useState
from hitsave.console import console

logger = logging.getLogger("hitsave.webview-server")


def Counter(props: int) -> Spec:
    i, set_i = useState(props)
    return h(
        "div",
        {},
        [
            h("button", dict(onClick=lambda _: set_i(i + 1)), "+"),
            str(i),
            h("button", dict(onClick=lambda _: set_i(i - 1)), "-"),
        ],
    )


def HelloWorld(props: dict[Any, Any]) -> Spec:
    sess: ProxySession = props.get("session")  # type: ignore
    counters, set_counters = useState([1])

    def mk_counter(i):
        return h(
            "li",
            {},
            [
                h(Counter, i),
                h(
                    "button",
                    dict(
                        onClick=lambda _: set_counters(
                            lambda cs: [c for c in cs if c != i]
                        )
                    ),
                    "remove",
                ),
            ],
            key=str(i),
        )

    return [
        h("h1", {"style": {"color": "red"}}, "Hello world"),
        h("p", {}, "result:", str(sess.workspace_dir)),
        h(
            "ol",
            {},
            [mk_counter(i) for i in counters],
        ),
        h(
            "button",
            dict(onClick=lambda _: set_counters(lambda cs: [*cs, max([0, *cs]) + 1])),
            "new_counter",
        ),
    ]


class WebviewServer(RpcServer):
    def __init__(self, transport: Transport, proxy_session: ProxySession):
        super().__init__(transport=transport)
        self.proxy_session = proxy_session
        self.reactor = Reactor(spec=h(HelloWorld, {"session": self.proxy_session}))
        self.reactor.initialize()
        self.dispatcher.register("render")(self.render)
        self.dispatcher.register("event")(self.handle_event)
        self.patcher_loop_task = asyncio.create_task(self.patcher_loop())

    async def render(self, params):
        return self.reactor.render()

    async def handle_event(self, params: EventArgs):
        return self.reactor.handle_event(params)

    async def patcher_loop(self):
        while True:
            logger.debug("patcher_loop: waiting for patches")
            patches = await self.reactor.get_patches()
            if len(patches) > 0:
                try:
                    await self.request("patch", [])  # [todo] send encoded patches
                except Exception as e:
                    # [todo] this is for debugging only
                    logger.error(e)
                    console.print_exception()

from collections import defaultdict
from dataclasses import dataclass
import asyncio
from pathlib import Path
import sys
import logging
import pprint
import json
import os
from typing import Literal, Optional, Union
import urllib.parse
import importlib
import importlib.util
from uuid import UUID, uuid4
from hitsave.decorator import SavedFunction
from hitsave.server.jsonrpc import Dispatcher, RpcServer, get_initialization_message
from hitsave.server.lsp import LanguageServer
import hitsave.server.lsptypes as lsp
from hitsave.server.proxy_session import ProxySession
from hitsave.server.transport import (
    AsyncStreamTransport,
    Transport,
    create_pipe_streams,
)
from hitsave.server.webviewserver import WebviewServer
from hitsave.session import Session
from hitsave.symbol import module_name_of_file
from hitsave.console import logger

# logger = logger.getChild("server")

# ref: https://stackoverflow.com/questions/64303607/python-asyncio-how-to-read-stdin-and-write-to-stdout


class MetaServer:
    """The server of servers on your local machine

    It manages:
    - LSP connections
    - Kernel connections
    - Webview connections
    - User-process connections

    In the future you will also be able to use it to host a cloud instance.

    This has nothing to do with the metaverse.
    """

    def __init__(
        self,
        websocket_port=7787,
        lsp_port=7797,
    ):
        self.websocket_port = websocket_port
        self.lsp_port = lsp_port
        self.language_servers = {}
        self.proxy_sessions = {}

    async def on_websocket_connection(self, websocket):
        """This is called for the lifetime of a websocket connection."""
        init_params = await get_initialization_message(websocket)
        if init_params.type == "webview":
            assert init_params.workspace_dir is not None
            logger.info(f"New webview connection for {init_params.workspace_dir}.")
            path = Path(init_params.workspace_dir)
            proxy_session = self.proxy_sessions[path]
            assert proxy_session is not None
            server = WebviewServer(websocket, proxy_session=proxy_session)
            await server.serve_forever()
        else:
            raise NotImplementedError()

    async def on_lsp_connection(self, reader, writer):
        logger.info("New LSP connection over socket.")
        transport = AsyncStreamTransport(reader, writer)
        await self.run_lsp(transport)

    async def run_lsp(self, transport):
        server = LanguageServer(transport)
        t = asyncio.create_task(server.serve_forever())
        init_params = await server.initialize_params
        folders = init_params.workspaceFolders
        assert folders is not None and len(folders) > 0
        folder = folders[0]
        uri = urllib.parse.urlparse(folder.uri)
        assert uri.netloc == ""
        assert uri.scheme == "file"
        path = Path(uri.path)
        logger.info(f"LSP at {path} connected.")
        # [todo] the idea is that this class keeps a set of ProxySessions
        # running for every folder and python executable that we want.
        # So here for the given path we need to make sure that we are using the right version of python.
        ps = ProxySession(workspace_dir=path)
        self.proxy_sessions[path] = ps
        server.session = ps
        # [todo] also pass the relevant python executable + env
        assert path not in self.language_servers
        self.language_servers[path] = server
        await t
        del self.language_servers[path]

    async def run_lsp_tcp(self):
        assert isinstance(self.lsp_port, int)
        server = await asyncio.start_server(
            self.on_lsp_connection, "127.0.0.1", self.lsp_port
        )
        async with server:
            addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
            logger.info(f"Listening with LSP protool on {addrs}")
            await server.serve_forever()

    async def run_lsp_stdio(self):
        reader, writer = await create_pipe_streams(
            in_pipe=sys.stdin, out_pipe=sys.stdout
        )
        transport = AsyncStreamTransport(reader, writer)
        await self.run_lsp(transport)

    async def run_forever(self):
        """Runs the language server.

        If lsp_port = 'stdio', then the LSP listens on stdin and stdout.
        There is also a websocket server at 7787 that the webview can connect to.
        """
        import websockets

        async with websockets.serve(self.on_websocket_connection, "localhost", self.websocket_port):  # type: ignore
            if self.lsp_port == "stdio":
                await self.run_lsp_stdio()
            else:
                await self.run_lsp_tcp()


def main():
    logger.setLevel(logging.INFO)
    # logging.basicConfig(level=logging.DEBUG, handlers=[])
    metaserver = MetaServer()
    asyncio.run(metaserver.run_forever(), debug=True)


if __name__ == "__main__":
    main()

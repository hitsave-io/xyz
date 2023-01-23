from dataclasses import dataclass
import asyncio
import sys
import logging
import pprint
import json
import os
from typing import Optional
import urllib.parse
import importlib
import importlib.util
from hitsave.decorator import SavedFunction
from hitsave.server.lsp import LanguageServer, method
from hitsave.server.lsptypes import (
    CodeLensParams,
    InitializeParams,
    Range,
    TextDocumentIdentifier,
)
from hitsave.server.transport import PipeTransport
from hitsave.server.webviewserver import WebviewServer
from hitsave.session import Session
from hitsave.symbol import module_name_of_file


logger = logging.getLogger("hitsave.server")

# ref: https://stackoverflow.com/questions/64303607/python-asyncio-how-to-read-stdin-and-write-to-stdout


async def register_websocket(websocket):
    logging.info("New connection")
    server = WebviewServer(websocket)
    await server.start()


async def run():
    """Runs the language server.

    The LSP listens on stdin and stdout.
    There is also a websocket server at 7787 that the webview can connect to.
    """
    import websockets

    async with websockets.serve(register_websocket, "localhost", 7787):  # type: ignore
        # connect up the stdin, stdout for lsp
        tr = PipeTransport(in_pipe=sys.stdin, out_pipe=sys.stdout)
        await tr.connect()
        server = LanguageServer(tr)
        await server.start()  # runs forever


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    asyncio.run(run())


if __name__ == "__main__":
    main()

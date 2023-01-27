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
from hitsave.codegraph import Binding
from hitsave.decorator import SavedFunction
from hitsave.server.hsptypes import InitParams
from hitsave.server.jsonrpc import Dispatcher, RpcServer, get_initialization_message
import hitsave.server.lsptypes as lsp
from hitsave.server.transport import (
    AsyncStreamTransport,
)
from hitsave.symbol import Symbol, module_name_of_file
from hitsave.util import ofdict

logger = logging.getLogger("hitsave.server.proxy_session")


@dataclass
class SavedFunctionInfo:
    line_start: int
    """ Line number of the start of the saved function """
    line_end: int
    """ Line number of the end of the saved function """
    name: str
    """ Name of the saved function """
    is_experiment: bool
    symbol: Symbol
    dependencies: dict


class ProxySession:
    server: Optional[RpcServer] = None
    proc: Optional[asyncio.subprocess.Process] = None

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.dispatcher = Dispatcher()
        self.create_server_lock = asyncio.Lock()

    async def create_server(self):
        # [todo] make sure that there is not already a kernel running?
        # we could also in principle be managing kernels for different projects.
        # [todo] just assume a virtual env in `.env` for now.
        virtual_env = self.workspace_dir / ".env"
        PATH = os.environ.get("PATH")
        assert PATH is not None
        PATH = f"{virtual_env}/bin:{PATH}"
        py = virtual_env / "bin" / "python"

        proc = await asyncio.create_subprocess_exec(
            py,
            "-m",
            "hitsave",
            "kernel",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace_dir),
            env={"PATH": PATH, "VIRTUAL_ENV": str(virtual_env)},
        )
        self.proc = proc
        logger.info(f"Started kernel with PID {proc.pid}")
        reader, writer = proc.stdout, proc.stdin
        err_reader = proc.stderr
        assert isinstance(reader, asyncio.StreamReader)
        assert isinstance(err_reader, asyncio.StreamReader)
        assert isinstance(writer, asyncio.StreamWriter)
        transport = AsyncStreamTransport(reader, writer)
        server = RpcServer(transport, dispatcher=self.dispatcher)

        async def error_pipe():
            while True:
                buf = await err_reader.readline()
                if not buf:
                    break
                msg = buf.decode().strip()
                logger.debug(f"kernel {proc.pid}: {msg}")

        async def _serve():
            await server.serve_forever()
            logger.info("Kernel exited.")
            self.server = None

        self.server = server
        asyncio.create_task(_serve())
        asyncio.create_task(error_pipe())
        init_params = InitParams(
            type="proxy-session", workspace_dir=str(self.workspace_dir)
        )
        init_result = await self.server.request("initialize", init_params)
        return server

    async def get_server(self) -> RpcServer:
        async with self.create_server_lock:
            if self.server is None:
                self.server = await self.create_server()
        return self.server

    async def invalidate(self, params):
        if self.server is not None:
            result = await self.server.request("invalidate", params)
            if result:
                logger.info("Invalidated. Shutting down kernel.")
                self.server = None
                # server will exit on its own and future requests will fail.
                # in-flight requests will raise a code-changed error.

    async def get_info_for_file(
        self, params: lsp.TextDocumentIdentifier
    ) -> list[SavedFunctionInfo]:
        server = await self.get_server()
        results: list = await server.request("get_info_for_file", params)
        results = ofdict(list[SavedFunctionInfo], results)
        return results

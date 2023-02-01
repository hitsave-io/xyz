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
import hitsave.server.hsptypes as hsp
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
    filepath: Path


class ProxySession:
    """ProxySession is the object that contains all of the information about the current HitSave project.

    - Connection to local sqlite server.
    - Connection to a 'Kernel' which maintains the codegraph and hot-reloading
    - Marshalling events between Webview, LSP, Cloud, Running user processes.

    [Todo] rename to WorkspaceServer
    """

    active_sessions: dict[Path, "ProxySession"] = {}
    tasks: set[asyncio.Task]
    server: Optional[RpcServer] = None
    proc: Optional[asyncio.subprocess.Process] = None

    @classmethod
    def get(cls, workspace_dir):
        if workspace_dir not in cls.active_sessions:
            cls.active_sessions[workspace_dir] = ProxySession(workspace_dir)
        return cls.active_sessions[workspace_dir]

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.dispatcher = Dispatcher()
        self.create_kernel_lock = asyncio.Lock()
        self.tasks = set()

    def on_document_change(
        self, path: Path, contentChanges: list[lsp.TextDocumentContentChangeEvent]
    ):
        logger.debug(f"Document changed: {path}")

    def on_open_document(self, path: Path):
        """Call this to tell the session that the editor just opened a doc."""
        logger.debug(f"Document opened: {path}")

    def on_focus(self, params: Union[lsp.TextDocumentPositionParams, hsp.FocusParams]):
        """This is called when the user clicks on a particular symbol."""
        logger.debug(f"Focus: {params}")

    async def create_kernel(self):
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
                # [todo] forward as LogRecords rather than from stderr stream.
                # logger.debug(f"kernel {proc.pid}: {msg}")

        async def _serve():
            await server.serve_forever()
            logger.info("Kernel exited.")
            self.server = None

        self.server = server
        self._with_task(_serve())
        self._with_task(error_pipe())
        init_params = hsp.InitParams(
            type="proxy-session", workspace_dir=str(self.workspace_dir)
        )
        init_result = await self.server.request("initialize", init_params)
        await self.server.notify("initialized", {})
        return server

    def _with_task(self, coro):
        # polyfill until we get TaskGroups
        t = asyncio.create_task(coro)
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)

    async def get_server(self) -> RpcServer:
        async with self.create_kernel_lock:
            if self.server is None:
                await asyncio.shield(self.create_kernel())
        assert self.server is not None
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

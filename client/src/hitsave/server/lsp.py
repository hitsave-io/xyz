from asyncio import Future
import os
import logging
from typing import Optional
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import InitializeParams
from hitsave.server.proxy_session import ProxySession, SavedFunctionInfo
from hitsave.server.transport import Transport
import sys
import urllib.parse
import importlib
import importlib.util
from hitsave.decorator import SavedFunction
import hitsave.server.lsptypes as lsp
from hitsave.symbol import module_name_of_file
from hitsave.util import ofdict

logger = logging.getLogger("hitsave.lsp")


class LanguageServer(RpcServer):
    initialize_params: Future[lsp.InitializeParams]
    session: Optional[ProxySession] = None

    def __init__(self, transport: Transport):
        self.session = None
        self.initialize_params = Future()
        super().__init__(transport=transport)
        self.dispatcher.register("initialize")(self.lsp_initialize)
        self.dispatcher.register("textDocument/didChange")(self.lsp_document_change)
        self.dispatcher.register("textDocument/didOpen")(self.lsp_document_open)
        self.dispatcher.register("textDocument/didClose")(self.lsp_document_close)
        self.dispatcher.register("textDocument/codeLens")(self.lsp_code_lens)

    async def lsp_initialize(
        self,
        params: lsp.InitializeParams,
    ):
        logger.debug(f"Initializing at {os.getcwd()} for PID:{params.processId}")
        self.initialize_params.set_result(params)
        return {"capabilities": {"codeLensProvider": {"resolveProvider": False}}}

    async def lsp_document_change(
        self,
        params: lsp.DidChangeTextDocumentParams,
    ):
        # [todo] invalidate session here.
        logger.info(f"document change detected")

    async def lsp_document_close(
        self,
        params: lsp.TextDocumentParams,
    ):
        logger.info("Document closed")

    async def lsp_document_open(
        self,
        params: lsp.TextDocumentParams,
    ):
        logger.info("document opened")

    async def lsp_code_lens(
        self,
        params: lsp.CodeLensParams,
    ):
        # [todo] lives in own file.
        assert self.session is not None
        items = await self.session.get_info_for_file(params.textDocument)

        rs = []
        for sfi in items:
            # ref: https://docs.python.org/3/library/inspect.html#types-and-members
            ln = sfi.line_start - 1
            r = lsp.Range.mk(ln, 0, ln, len("@save"))
            rs.append(
                {
                    "range": r,
                    "command": {
                        "title": f"{len(sfi.dependencies) - 1} dependencies",
                        "command": "hitsave.openInfo",
                    },
                }
            )
        return rs

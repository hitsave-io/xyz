from asyncio import Future
import os
import logging
from pathlib import Path
from typing import Optional, Union
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import InitializeParams, TextDocumentSyncKind
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
import hitsave.server.hsptypes as hsp
from hitsave.console import logger


class LanguageServer(RpcServer):
    workspace_dir: Path
    initialized: bool
    session: ProxySession

    def __init__(self, transport: Transport):
        super().__init__(transport=transport)
        self.initialized = False
        self.dispatcher.register("initialize")(self.on_initialize)
        self.dispatcher.register("initialized")(self.on_client_initialized)
        self.dispatcher.register("textDocument/didChange")(self.on_document_change)
        self.dispatcher.register("textDocument/didOpen")(self.on_document_open)
        self.dispatcher.register("textDocument/didClose")(self.on_document_close)
        self.dispatcher.register("textDocument/codeLens")(self.on_code_lens)

        self.dispatcher.register("hitsave/focus")(self.focus)

    def on_client_initialized(self, params):
        assert hasattr(self, "workspace_dir")
        assert hasattr(self, "session")
        logger.debug(f"{self}'s client initialized")

    async def focus(
        self, params: Union[lsp.TextDocumentPositionParams, hsp.FocusParams]
    ):
        self.session.on_focus(params)

    async def on_initialize(
        self,
        params: lsp.InitializeParams,
    ):
        folders = params.workspaceFolders
        assert folders is not None and len(folders) > 0
        if len(folders) > 1:
            logger.warn("LSP workspace on multiple folders not yet supported.")
        folder = folders[0]
        path = lsp.path_of_uri(folder.uri)

        self.workspace_dir = path
        self.session = ProxySession.get(self.workspace_dir)
        # [todo] check params.capabilities.codeLens
        self.initialized = True
        logger.debug(f"{self} initialized")
        return lsp.InitializeResult(
            serverInfo=lsp.ClientInfo(),
            capabilities=lsp.ServerCapabilities(
                textDocumentSync=lsp.TextDocumentSyncOptions(
                    openClose=True, change=lsp.TextDocumentSyncKind.incremental
                ),
                codeLensProvider=lsp.CodeLensOptions(resolveProvider=False),
            ),
        )

    async def on_document_change(
        self,
        params: lsp.DidChangeTextDocumentParams,
    ):
        # [todo] invalidate session here.
        self.session.on_document_change(
            path=lsp.path_of_uri(params.textDocument.uri),
            contentChanges=params.contentChanges,
        )

    async def on_document_close(
        self,
        params: lsp.TextDocumentParams,
    ):
        logger.info(f"{self} Document {params.textDocument} closed")

    async def on_document_open(
        self,
        params: lsp.TextDocumentParams,
    ):
        path = lsp.path_of_uri(params.textDocument.uri)
        self.session.on_open_document(path)

    async def on_code_lens(
        self,
        params: lsp.CodeLensParams,
    ):
        assert self.initialized
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
                        "command": "hitsave.showFunction",
                        "arguments": [str(sfi.symbol)],
                    },
                }
            )
        return rs

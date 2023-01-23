import os
import logging
from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.server.lsptypes import InitializeParams
from hitsave.server.transport import Transport
import sys
import urllib.parse
import importlib
import importlib.util
from hitsave.decorator import SavedFunction
from hitsave.server.lsptypes import (
    CodeLensParams,
    InitializeParams,
    Range,
)
from hitsave.session import Session
from hitsave.symbol import module_name_of_file

logger = logging.getLogger("hitsave.lsp")

LSP_DISPATCHER = Dispatcher()


def method(name=None):
    return LSP_DISPATCHER.register(name)


class LanguageServer(RpcServer):
    def __init__(self, transport: Transport):
        super().__init__(transport=transport, dispatcher=LSP_DISPATCHER)


@method()
async def initialize(params: InitializeParams):
    logger.debug(f"Initializing at {os.getcwd()}\n{params}")
    return {"capabilities": {"codeLensProvider": {"resolveProvider": False}}}


@method("textDocument/didChange")
async def documentDidChange(params):
    pass


@method("textDocument/didOpen")
async def documentDidOpen(params):
    pass


@method("textDocument/didClose")
async def documentDidClose(params):
    pass


@method("textDocument/codeLens")
async def codelens(params: CodeLensParams):
    uri = urllib.parse.urlparse(params.textDocument.uri)
    assert uri.scheme == "file"
    assert uri.netloc == ""
    module_name = module_name_of_file(uri.path)
    if module_name is None:
        logger.error(f"No such module for {uri.path}")
        return []
    logger.info(f"Resolved module {module_name} from {uri.path}")
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, uri.path)
        assert spec is not None
        module = importlib.import_module(module_name)
    module = importlib.reload(module)
    # [todo] need a way to invalidate the codegraph of the changed modules here.
    logger.debug(
        f"module has {len(module.__dict__)} entries: {list(module.__dict__.keys())}"
    )
    rs = []
    for k, sf in module.__dict__.items():
        if not isinstance(sf, SavedFunction):
            continue
        logger.debug(f"Found {k}.")
        f = sf.func
        sess = Session.current()
        deps = set(sess.codegraph.get_dependencies_obj(f))
        # ref: https://docs.python.org/3/library/inspect.html#types-and-members
        ln = f.__code__.co_firstlineno - 1
        r = Range.mk(ln, 0, ln, len("@save"))
        rs.append(
            {
                "range": r,
                "command": {
                    "title": f"{len(deps) - 1} dependencies",
                    "command": "hitsave.helloWorld",
                },
            }
        )
    return rs

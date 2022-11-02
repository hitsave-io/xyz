from dataclasses import dataclass
import asyncio
import sys
import logging
import pprint
import json
import os
import urllib.parse
import importlib
import importlib.util
from hitsave.session import Session
from hitsave.codegraph import CodeVertex, module_name_of_file
from hitsave.decorator import SavedFunction
from hitsave.lsp import Range, TextDocumentIdentifier, method, LanguageServer

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

logger = logging.getLogger("hitsave.server")


@method()
async def initialize(params):
    logger.debug(f"Initializing at {os.getcwd()}")
    return {"capabilities": {"codeLensProvider": {"resolveProvider": False}}}


@dataclass
class CodeLensParams:
    textDocument: TextDocumentIdentifier


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
        deps = len(list(Session.current().codegraph.get_dependencies_obj(f)))
        # ref: https://docs.python.org/3/library/inspect.html#types-and-members
        ln = f.__code__.co_firstlineno - 1
        r = Range.mk(ln, 0, ln, len("@memo"))
        rs.append(
            {
                "range": r,
                "command": {
                    "title": f"{deps - 1} dependencies",
                    "command": "hitsave.helloWorld",
                },
            }
        )
    return rs


# ref: https://stackoverflow.com/questions/64303607/python-asyncio-how-to-read-stdin-and-write-to-stdout


async def connect():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    return reader, writer


async def run():
    reader, writer = await connect()
    server = LanguageServer(reader=reader, writer=writer)
    await server.start()


def main():
    asyncio.run(run())

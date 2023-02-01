import asyncio
from dataclasses import dataclass
import inspect
import logging
from pathlib import Path
import sys
from types import ModuleType
from typing import Union
from hitsave.config import Config
from hitsave.decorator import SavedFunction
from hitsave.server.hsptypes import InitParams
from hitsave.server.jsonrpc import RpcServer
import urllib.parse
from hitsave.server.proxy_session import SavedFunctionInfo
from hitsave.server.transport import (
    AsyncStreamTransport,
    Transport,
    create_pipe_streams,
)
import importlib
import importlib.util
from hitsave.session import Session
from hitsave.symbol import Symbol, module_name_of_file
import hitsave.server.lsptypes as lsp
import os

logger = logging.getLogger("hitsave.kernel")


class KernelServer(RpcServer):
    """This runs in its own sub-process. It gives all of the information to do with the Python source for HitSave.

    The idea is that when the user changes their sourcecode, you need to recompute the dependencies of the code.
    It is sometimes possible to do this with a bit of hot-reloading, particularly if you have a stream of edits from vscode.
    However in general you need to restart the Python process and reload all of the modules from zero.
    Hence it makes sense to run the code that computes dependencies in its own sub-process so that it can be restarted.

    Todo:
    * [todo] log records should be fed to parent process.
    """

    def __init__(self, transport: Transport):
        super().__init__(transport=transport)
        self.dispatcher.register()(self.initialize)
        self.dispatcher.register()(self.get_info_for_file)
        self.dispatcher.register()(self.get_info)
        self.config = Config.default()
        Config.set_current(self.config)
        self.session = Session()
        Session.set_current(self.session)

    async def initialize(self, params):
        logger.info(f"connected and initialized on PID-{os.getpid()} at {os.getcwd()}.")
        return InitParams(
            clientInfo=lsp.ClientInfo("hitsave"),
            type="kernel",
            workspace_dir=str(self.config.workspace_dir),
        )

    def get_info(self, sf: Union[Symbol, SavedFunction]):
        if not isinstance(sf, SavedFunction):
            assert isinstance(sf, Symbol)
            sf = sf.get_bound_object()  # type: ignore
            assert isinstance(sf, SavedFunction), "not a saved function"
        f = sf.func
        symbol = Symbol.of_object(f)
        sess = self.session
        deps = sess.fn_deps(symbol)
        deps = {str(k): v.todict() for k, v in deps.items()}
        # ref: https://docs.python.org/3/library/inspect.html#types-and-members
        lines, line_start = inspect.getsourcelines(f)
        filepath = getattr(sf.symbol.get_module(), "__file__")
        return SavedFunctionInfo(
            line_start=line_start,
            line_end=line_start + len(lines),
            name=f.__name__,
            symbol=symbol,
            is_experiment=sf.is_experiment,
            dependencies=deps,
            filepath=Path(filepath),
        )

    def get_info_for_module(self, module: ModuleType):
        path = getattr(module, "__file__")
        rs: list[SavedFunctionInfo] = []
        for k, sf in module.__dict__.items():
            if not isinstance(sf, SavedFunction):
                continue
            rs.append(self.get_info(sf))
        return rs

    def get_info_for_file(
        self, params: lsp.TextDocumentIdentifier
    ) -> list[SavedFunctionInfo]:
        uri = urllib.parse.urlparse(params.uri)
        assert uri.scheme == "file"
        assert uri.netloc == ""
        path = Path(uri.path)
        module_name = module_name_of_file(path)
        if module_name is None:
            logger.error(f"No such module for {path}")
            return []
        module = sys.modules.get(module_name)
        if module is None:
            spec = importlib.util.spec_from_file_location(module_name, path)
            assert spec is not None
            module = importlib.import_module(module_name)
        return self.get_info_for_module(module)


async def run():
    reader, writer = await create_pipe_streams(sys.stdin, sys.stdout)
    transport = AsyncStreamTransport(reader, writer)
    c = KernelServer(transport)
    await c.serve_forever()


def main():
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
    asyncio.run(run())


if __name__ == "__main__":
    main()

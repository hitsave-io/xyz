import asyncio
import sys
import logging
from hitsave.server.lsp import LanguageServer
from hitsave.server.transport import (
    AsyncStreamTransport,
    create_pipe_streams,
)
from hitsave.server.webviewserver import WebviewServer
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

    async def on_websocket_connection(self, websocket):
        """This is called for the lifetime of a websocket connection."""
        server = WebviewServer(websocket)
        await server.serve_forever()

    async def on_lsp_connection(self, reader, writer):
        transport = AsyncStreamTransport(reader, writer)
        await self.run_lsp(transport)

    async def run_lsp(self, transport):
        server = LanguageServer(transport)
        await server.serve_forever()

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
    logger.setLevel(logging.DEBUG)
    # logging.basicConfig(level=logging.DEBUG, handlers=[])
    metaserver = MetaServer()
    asyncio.run(metaserver.run_forever(), debug=True)


if __name__ == "__main__":
    main()

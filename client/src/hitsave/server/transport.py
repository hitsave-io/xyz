from typing import Awaitable, Protocol
import asyncio
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class Transport(Protocol):
    """RPC-transport. (not to be confused with )"""

    def recv(self) -> Awaitable[bytes]:
        ...

    def send(self, data: bytes) -> Awaitable[None]:
        ...


async def create_pipe_streams(in_pipe, out_pipe):
    """Converts a pair of pipes into a reader/writer async pair."""
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, in_pipe)
    w_transport, w_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, out_pipe
    )
    writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
    return reader, writer


class AsyncStreamTransport(Transport):
    """Create a transport from a StreamReader, StreamWriter pair.

    We assume the message protocol is that described in LSP
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#baseProtocol
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

    async def recv(self):
        """Recieves data from the stream. If EOF is reached, raises EOFError."""
        # read the header
        header = {}
        while True:
            line = await self.reader.readline()
            if line == b"":
                assert self.reader.at_eof()
                if len(header) == 0:
                    raise EOFError("End of stream.")
                else:
                    raise asyncio.IncompleteReadError(partial=line, expected=None)
            line = line.decode().rstrip()
            if line == "":
                break
            k, v = line.split(":", 1)
            header[k.lower()] = v
        content_length = header.get("content-length")
        if content_length is None:
            raise ValueError("No content-length header")
        content_length = int(content_length)
        data = await self.reader.readexactly(content_length)
        return data

    async def send(self, data: bytes, header={}):
        header["Content-Length"] = len(data)
        header = "".join(f"{k}:{v}\r\n" for k, v in header.items())
        header += "\r\n"
        self.writer.write(header.encode())
        self.writer.write(data)

from typing import Awaitable, Protocol
import asyncio


class Transport(Protocol):
    def recv(self) -> Awaitable[bytes]:
        ...

    def send(self, data: bytes) -> Awaitable[None]:
        ...


class PipeTransport(Transport):
    """Takes a non-messaging pair of TextIO streams and makes a messaging transport from them.

    We assume the message protocol is that described in LSP
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#baseProtocol
    """

    def __init__(self, in_pipe, out_pipe):
        self.in_pipe = in_pipe
        self.out_pipe = out_pipe

    async def connect(self):
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, self.in_pipe)
        w_transport, w_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, self.out_pipe
        )
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, loop)
        self.reader = reader
        self.writer = writer
        self.is_connected = True

    async def recv(self):
        assert self.is_connected
        # read the header
        header = {}
        while True:
            line = await self.reader.readline()
            line = line.decode().rstrip()
            if line == "":
                break
            k, v = line.split(":", 1)
            header[k] = v
        content_length = header.get("Content-Length")
        assert content_length is not None
        content_length = int(content_length)
        assert content_length > 0
        data = await self.reader.read(content_length)
        return data

    async def send(self, data: bytes, header={}):
        assert self.is_connected
        header["Content-Length"] = len(data)
        header = "\r\n".join(f"{k}:{v}" for k, v in header.items())
        header += "\r\n"
        self.writer.write(header.encode())
        self.writer.write(data)

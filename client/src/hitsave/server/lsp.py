from asyncio import Future, StreamReader, StreamWriter
import asyncio
from functools import singledispatch
from dataclasses import MISSING, asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, Union, Coroutine
import inspect
import logging
from hitsave.util.ofdict import MyJsonEncoder, ofdict
import json

logger = logging.getLogger("hitsave.lsp")


class ErrorCode(Enum):
    parse_error = -32700
    invalid_request = -32600
    method_not_found = -32601
    invalid_params = -32602
    internal_error = -32603


encoder = MyJsonEncoder()


@dataclass
class Request:
    method: str
    id: Optional[Union[str, int]] = field(default=None)
    params: Optional[Any] = field(default=None)

    @property
    def is_notification(self):
        return self.id is None

    def to_bytes(self):
        return encoder.encode(self).encode()


@dataclass
class ResponseError:
    code: ErrorCode
    message: str
    data: Optional[Any] = field(default=None)


@dataclass
class ResponseException(Exception):
    code: ErrorCode
    message: str
    id: Any
    data: Optional[Any] = field(default=None)


@dataclass
class Response:
    """JSON-RPC response.

    https://www.jsonrpc.org/specification#response_object
    """

    id: Any = field(default=None)
    result: Optional[Any] = field(default=None)
    error: Optional[ResponseError] = field(default=None)
    jsonrpc: str = field(default="2.0")

    def to_bytes(self):
        return encoder.encode(self).encode()


METHODS = {}


def method(name: Optional[str] = None):
    def core(fn):
        funcname = name or fn.__name__
        sig = inspect.signature(fn)
        if len(sig.parameters) == 0:
            T = Any
        else:
            P = next(iter(sig.parameters.values()))
            T = P.annotation
            if T is inspect.Parameter.empty:
                T = Any

        async def g(req: Request):
            try:
                if len(sig.parameters) == 0:
                    result = await fn()
                else:
                    assert req.params is not None
                    p = ofdict(T, req.params)
                    result = await fn(p)
                if req.is_notification:
                    return
                return Response(id=req.id, result=result)
            except Exception as e:
                id = getattr(req, "id", None)
                msg = getattr(e, "message", None) or str(e)
                err = ResponseError(message=msg, code=ErrorCode.internal_error)
                return Response(id=id, error=err)

        METHODS[funcname] = g

        return fn

    return core


class LanguageServer:
    reader: StreamReader
    writer: StreamWriter
    request_counter: int
    in_flight: Dict[str, Future[Any]]

    def __init__(self, reader: StreamReader, writer: StreamWriter):
        self.reader = reader
        self.writer = writer
        self.in_flight = {}
        self.request_counter = 1000

    def send(self, r: Union[Response, Request]):
        bs = r.to_bytes()
        header = f"Content-Length:{len(bs)}\r\n\r\n"
        self.writer.write(header.encode())
        self.writer.write(bs)

    async def notify(self, method: str, params: Optional[Any]):
        req = Request(method=method, params=params)
        self.send(req)

    async def request(self, method: str, params: Optional[Any]) -> Awaitable[Any]:
        self.request_counter += 1
        id = f"server-{self.request_counter}"
        req = Request(method=method, id=id, params=params)
        fut = asyncio.get_running_loop().create_future()
        self.in_flight[id] = fut
        self.send(req)
        return fut

    async def start(self):
        """Runs forever. Serves your client."""
        while True:
            # read the header
            header = {}
            while True:
                line = await self.reader.readline()
                line = line.decode().rstrip()
                if line == "":
                    break
                k, v = line.split(":", 1)
                header[k] = v
            content_len = header.get("Content-Length")
            assert content_len is not None
            res = await self.reader.read(int(content_len))
            try:
                res = json.loads(res)
            except json.JSONDecodeError as e:
                response = Response(
                    error=ResponseError(message=e.msg, code=ErrorCode.parse_error)
                )
                self.send(response)
                continue
            if "result" in res or "error" in res:
                res = ofdict(Response, res)
                fut = self.in_flight.pop(res.id)
                if res.error is not None:
                    fut.set_exception(
                        ResponseException(
                            id=res.id,
                            message=res.error.message,
                            code=res.error.code,
                            data=res.error.data,
                        )
                    )
                elif res.result is not None:
                    fut.set_result(res.result)
                else:
                    raise TypeError(f"badly formed {res}")
            else:
                req = ofdict(Request, res)
                logger.debug(f"← {req.id} {req.method}")
                handler = METHODS.get(req.method)
                if handler is None:
                    err = ResponseError(
                        code=ErrorCode.method_not_found,
                        message=f"No such method {req.method}",
                    )
                    response = Response(id=req.id, error=err)
                    self.send(response)
                    continue
                resp: Optional[Response] = await handler(req)
                if resp is not None:
                    logger.debug(f"→ {req.id} {resp}")
                    self.send(resp)


""" # LSP Data types """


@dataclass
class TextDocumentIdentifier:
    uri: str
    version: Optional[int]


@dataclass
class Position:
    line: int
    character: int


@dataclass
class Range:
    start: Position
    end: Position

    @classmethod
    def mk(cls, l0: int, c0: int, l1: int, c1: int):
        return cls(Position(l0, c0), Position(l1, c1))


@dataclass
class TextDocumentContentChangeEvent:
    range: Optional[Range]
    rangeLength: Optional[int]
    text: str


@dataclass
class DidChangeTextDocumentParams:
    """
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#didChangeTextDocumentParams
    """

    textDocument: TextDocumentIdentifier
    contentChanges: List[TextDocumentContentChangeEvent]

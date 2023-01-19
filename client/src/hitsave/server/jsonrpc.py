from asyncio import Future, StreamReader, StreamWriter, Task
import asyncio
from functools import singledispatch
from dataclasses import MISSING, asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, Union, Coroutine
import inspect
import logging
from hitsave.util.ofdict import MyJsonEncoder, ofdict
import json
from hitsave.server.transport import Transport

logger = logging.getLogger("hitsave.json-rpc")


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


class Dispatcher:
    def __init__(self):
        self.methods = {}

    def __contains__(self, method):
        return method in self.methods

    def __getitem__(self, method):
        return self.methods[method]

    def param_type(self, method):
        fn = self.methods[method]
        sig = inspect.signature(fn)
        if len(sig.parameters) == 0:
            T = Any
        else:
            P = next(iter(sig.parameters.values()))
            T = P.annotation
            if T is inspect.Parameter.empty:
                T = Any
        return T

    def return_type(self, method):
        fn = self.methods[method]
        sig = inspect.signature(fn)
        a = sig.return_annotation
        if a is inspect.Signature.empty:
            return Any
        else:
            return a

    def register(self, name=None):
        def core(fn):
            funcname = name or fn.__name__
            self.methods[funcname] = fn
            return fn

        return core


class RpcServer:
    """Implementation of a JSON-RPC server."""

    dispatcher: Dispatcher
    transport: Transport
    request_counter: int
    in_flight: Dict[str, Future[Any]]
    tasks: set[Task]

    def __init__(self, transport: Transport, dispatcher=Dispatcher()):
        self.transport = transport
        self.dispatcher = dispatcher
        self.in_flight = {}
        self.request_counter = 1000
        self.tasks = set()

    async def send(self, r: Union[Response, Request]):
        await self.transport.send(r.to_bytes())

    async def notify(self, method: str, params: Optional[Any]):
        req = Request(method=method, params=params)
        await self.send(req)

    async def request(self, method: str, params: Optional[Any]) -> Awaitable[Any]:
        self.request_counter += 1
        id = f"server-{self.request_counter}"
        req = Request(method=method, id=id, params=params)
        fut = asyncio.get_running_loop().create_future()
        self.in_flight[id] = fut
        await self.send(req)
        return fut

    async def start(self):
        """Runs forever. Serves your client."""
        while True:
            data = await self.transport.recv()
            try:
                messages = json.loads(data)
                # res can be a batch
                if isinstance(messages, dict):
                    messages = [messages]
                assert isinstance(messages, list)
            except json.JSONDecodeError as e:
                response = Response(
                    error=ResponseError(message=e.msg, code=ErrorCode.parse_error)
                )
                await self.send(response)
                continue
            for message in messages:
                if "result" in message or "error" in message:
                    res = ofdict(Response, message)
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
                    req = ofdict(Request, message)
                    task = asyncio.create_task(self.handle(req))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)

    async def handle(self, req: Request):
        logger.debug(f"← {req.id} {req.method}")
        if req.method not in self.dispatcher:
            if req.is_notification:
                logger.debug(f"Unhandled notification {req.method}")
                return
            err = ResponseError(
                code=ErrorCode.method_not_found,
                message=f"No such method {req.method}",
            )
            response = Response(id=req.id, error=err)
            await self.send(response)
            return

        fn = self.dispatcher[req.method]
        try:
            params = ofdict(self.dispatcher.param_type(req.method), req.params)
            try:
                result = await fn(params)
                logger.debug(f"→ {req.id} {result}")
                await self.send(Response(id=req.id, result=result))
            except Exception as e:
                logger.error(e)
                if not req.is_notification:
                    await self.send(
                        Response(
                            id=req.id,
                            error=ResponseError(
                                message=str(e), code=ErrorCode.internal_error
                            ),
                        )
                    )
        except TypeError as e:
            if req.is_notification:
                logger.error(e)
            else:
                await self.send(
                    Response(
                        id=req.id,
                        error=ResponseError(
                            message=f"Invalid params for method {req.method}:\n  {str(e)}",
                            code=ErrorCode.invalid_params,
                        ),
                    )
                )

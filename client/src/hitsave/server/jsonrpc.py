from asyncio import Future, StreamReader, StreamWriter, Task
import asyncio
from functools import singledispatch, partial
from dataclasses import MISSING, asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Awaitable, Dict, List, Optional, Union, Coroutine
import inspect

from hitsave.util.ofdict import MyJsonEncoder, ofdict
import json
from hitsave.server.transport import Transport
from hitsave.server.hsptypes import InitParams
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
from hitsave.console import logger, console


class ErrorCode(Enum):

    ### JSON-RPC codes

    parse_error = -32700
    """ It doesn't parse as JSON """
    invalid_request = -32600
    """ You aren't allowed to do this. """
    method_not_found = -32601
    """ We don't have a method handler for that. """
    invalid_params = -32602
    """ Your parameters are not valid. (eg fields missing, bad types etc) """
    internal_error = -32603
    """ The internal server code messed up. """

    ### Codes specific to LSP

    server_not_initialized = -32002
    """ The server has not been initialized. """

    request_failed = -32803
    """A request failed but it was syntactically correct, e.g the
	 * method name was known and the parameters were valid. The error
	 * message should contain human readable information about why
	 * the request failed.
	 *"""

    server_cancelled = -32802
    """The server cancelled the request. This error code should
	 * only be used for requests that explicitly support being
	 * server cancellable."""

    content_modified = -32801
    """ Content got modified outside of normal conditions. """
    request_cancelled = -32800
    """ The client cancelled a request and the server has detected the cancel. """


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
    def __init__(self, methods={}, extra_kwargs={}):
        self.methods = methods
        self.extra_kwargs = extra_kwargs

    def __contains__(self, method):
        return method in self.methods

    def __getitem__(self, method):
        return partial(self.methods[method], **self.extra_kwargs)

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

    def with_kwargs(self, **kwargs):
        return Dispatcher(self.methods, {**self.extra_kwargs, **kwargs})


async def get_initialization_message(transport: Transport):
    data = await transport.recv()
    req = json.loads(data)
    assert isinstance(req, dict), "oops, it was batched and I haven't implemented that"
    req = ofdict(Request, req)
    params = ofdict(InitParams, req.params)
    await transport.send(Response(req.id, result={}).to_bytes())
    return params


server_count = 0

RequestId = Union[str, int]


class RpcServerStatus(Enum):
    preinit = 0
    running = 1
    shutdown = 2


class RpcServer:
    """Implementation of a JSON-RPC server.

    Following the conventions of LSP for extra functionality.

    [todo] special case for initialized; don't let other methods be called until initialized method is called.
    [todo] implement shutdown
    [todo] implement progress support
    [todo] rename to RpcConnection, then RpcServer and RpcClient handle the different conventions for
    lifecycle.
    [todo] add warnings if requests go unanswered for too long.
    """

    dispatcher: Dispatcher
    transport: Transport
    request_counter: int
    my_requests: Dict[int, Future[Any]]
    their_requests: Dict[RequestId, Task]
    notification_tasks: set[asyncio.Task]

    def __init__(self, transport: Transport, dispatcher=Dispatcher(), name=None):
        global server_count
        server_count += 1
        if name is None:
            self.name = f"<{type(self).__name__} {server_count}>"
        else:
            self.name = name
        self.transport = transport
        self.dispatcher = dispatcher
        self.my_requests = {}
        self.their_requests = {}
        self.request_counter = 1000
        self.notification_tasks = set()

    def __str__(self):
        return self.name

    async def send(self, r: Union[Response, Request]):
        await self.transport.send(r.to_bytes())

    async def notify(self, method: str, params: Optional[Any]):
        req = Request(method=method, params=params)
        await self.send(req)

    async def request(self, method: str, params: Optional[Any]) -> Any:
        self.request_counter += 1
        id = self.request_counter
        req = Request(method=method, id=id, params=params)
        fut = asyncio.get_running_loop().create_future()
        self.my_requests[id] = fut
        await self.send(req)
        result = await fut
        return result

    async def serve_forever(self):
        """Runs forever. Serves your client."""
        while True:
            try:
                data = await self.transport.recv()
                messages = json.loads(data)
                # res can be a batch
                if isinstance(messages, dict):
                    messages = [messages]
                if not isinstance(messages, list):
                    raise TypeError(f"expected list, got {type(messages)}")

            except (ConnectionClosedError, asyncio.IncompleteReadError) as e:
                logger.error(f"{self.name} transport closed with error: {e}")
                return
            except (ConnectionClosedOK, EOFError) as e:
                logger.info(f"{self.name} transport closed gracefully: {e}")
                return
            except json.JSONDecodeError as e:
                response = Response(
                    error=ResponseError(message=e.msg, code=ErrorCode.parse_error)
                )
                await self.send(response)
                continue
            except Exception as e:
                logger.error(f"Fatal {type(e)}: {e}")
                console.print_exception()
                break
            for message in messages:
                self._handle_message(message)

    def _handle_message(self, message: Any):
        if "result" in message or "error" in message:
            # this is a Response
            res = ofdict(Response, message)
            fut = self.my_requests.pop(res.id)
            if res.error is not None:
                fut.set_exception(
                    ResponseException(
                        id=res.id,
                        message=res.error.message,
                        code=res.error.code,
                        data=res.error.data,
                    )
                )
            else:
                fut.set_result(res.result)
        else:
            req = ofdict(Request, message)
            if req.method == "exit":
                # https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#exit
                logger.info(f"{self} recieved exit notification. Leaving server loop.")
                return
            task = asyncio.create_task(self._on_request(req))
            id = req.id
            if id is not None:
                self.their_requests[id] = task
                task.add_done_callback(lambda _: self.their_requests.pop(id))
            else:
                self.notification_tasks.add(task)
                task.add_done_callback(self.notification_tasks.discard)

    async def _on_request(self, req: Request) -> None:
        # logger.debug(f"{self.name} ←  {req.id} {req.method}")
        if req.method == "$/cancelRequest":
            assert req.is_notification
            assert isinstance(req.params, dict)
            t = self.my_requests.get(req.params["id"], None)
            if t is not None:
                t.cancel()
            return
        if req.method not in self.dispatcher:
            if req.is_notification:
                logger.debug(f"{self} Unhandled notification {req.method}")
                return
            msg = f"{self} No method named {req.method}"
            logger.error(msg)
            err = ResponseError(
                code=ErrorCode.method_not_found,
                message=msg,
            )
            response = Response(id=req.id, error=err)
            await self.send(response)
            return

        fn = self.dispatcher[req.method]
        T = self.dispatcher.param_type(req.method)
        try:
            params = ofdict(T, req.params)
        except TypeError as e:
            msg = f"{self} {req.method} {type(e)} failed to decode params to {T}: {e}"
            logger.error(msg)
            if not req.is_notification:
                await self.send(
                    Response(
                        id=req.id,
                        error=ResponseError(
                            message=msg,
                            code=ErrorCode.invalid_params,
                        ),
                    )
                )
            return
        try:
            result = fn(params)
            if asyncio.iscoroutine(result):
                result = await result
            if not req.is_notification:
                # logger.debug(f"{self.name} →  {req.id}")
                await self.send(Response(id=req.id, result=result))
        except asyncio.CancelledError as e:
            assert not req.is_notification
            await self.send(
                Response(
                    id=req.id,
                    error=ResponseError(
                        code=ErrorCode.request_cancelled, message=str(e)
                    ),
                )
            )

        except Exception as e:
            msg = f"{self} {req.method} {type(e)}: {e}"
            logger.error(msg)
            console.print_exception()
            if not req.is_notification:
                await self.send(
                    Response(
                        id=req.id,
                        error=ResponseError(message=msg, code=ErrorCode.internal_error),
                    )
                )

from dataclasses import asdict, dataclass, field, replace
import difflib
from enum import Enum
from io import BufferedReader
from typing import (
    IO,
    Any,
    ClassVar,
    Generic,
    Iterator,
    List,
    Literal,
    Optional,
    Dict,
    NamedTuple,
    Protocol,
    Set,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
)
import msgpack
import pickle
from hitsave.util import decorate_ansi, dict_diff, ofdict
import json
import requests
import os
import numpy as np
import logging
from requests.exceptions import ChunkedEncodingError
import shelve
import tempfile
from diskcache import Cache
from datetime import datetime
from uuid import UUID
from hitsave.codegraph import Symbol

logger = logging.getLogger("hitsave")


@dataclass
class EvalKey:
    """An EvalKey is a unique identifier for an evaluation"""

    fn_key: Symbol
    fn_hash: str
    args_hash: str

    def tojson(self):
        return json.dumps(asdict(self))

    def __str__(self):
        return f"{repr(self.fn_key)}|{self.fn_hash}|{self.args_hash}"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(repr(self))


R = TypeVar("R")


class EvalStatus(Enum):
    started = 0
    rejected = 1
    resolved = 2


@dataclass
class Eval:
    """The result of calling 'poll_eval' if successful."""

    key: EvalKey
    result_digest: str
    start_time: datetime
    """ time when the evaluation started  """
    elapsed_process_time: int
    """ process time elapsed in nanoseconds.  """
    is_experiment: bool

    status: EvalStatus
    deps: Dict[str, str]

    session_id: UUID
    user_id: UUID

    """ True when the saved function is an experiment (as opposed to a memo). Experiments should never be deleted by cache cleaners. """
    args: Optional[Dict[str, Any]] = field(default=None)

    @property
    def fn_key(self):
        return self.key.fn_key

    @property
    def fn_hash(self):
        return self.key.fn_hash

    @property
    def args_hash(self):
        return self.key.args_hash


class StoreMiss:
    """Represents a failure to get a key.

    there are a few different reasons why we might report a cache miss;
    - brand new function
    - same function key, but the function hash is different.
      In this case, it might be cool to report which function changed.
    - same function key, same function hash, new arguments
    also some local reasons why a lookup fails
    - the value exists, but there was a python decoding error (eg maybe the type changed)
    - python couldn't connect to the server
    """

    reason: str

    def __init__(self, reason):
        self.reason = reason


# [todo] move this out of types.
@dataclass
class CodeChanged(StoreMiss):
    _ALREADY_SEEN: ClassVar[Set[Tuple[str, str]]] = set()
    old_deps: Optional[Dict[str, str]]
    new_deps: Optional[Dict[str, str]]

    @property
    def reason(self):
        if self.old_deps is not None and self.new_deps is not None:
            lines = []
            diff = dict_diff(self.old_deps, self.new_deps)
            if len(diff.add) > 0:
                for x in diff.add:
                    lines.append(decorate_ansi("+++ " + x, fg="green"))
            if len(diff.rm) > 0:
                for x in diff.rm:
                    lines.append(decorate_ansi("--- " + x, fg="red"))
            if len(diff.mod) > 0:
                for x, (v1, v2) in diff.mod.items():
                    lines.append(decorate_ansi("~~~ " + x, fg="yellow"))
                    if (v1, v2) in CodeChanged._ALREADY_SEEN:
                        continue
                    CodeChanged._ALREADY_SEEN.add((v1, v2))
                    xs = list(
                        difflib.ndiff(
                            v1.splitlines(keepends=True), v2.splitlines(keepends=True)
                        )
                    )

                    def m(x: str):
                        if x.startswith("+"):
                            return decorate_ansi(x, fg="green")
                        if x.startswith("-"):
                            return decorate_ansi(x, fg="red")
                        return x

                    lines += "".join(map(m, xs)).split("\n")
            return "\n".join(lines)

        else:
            return "Function hash has changed."


# [todo] use same protocol as aiocache https://github.com/aio-libs/aiocache
# [todo] rename to StoreAPI, make this the general interface for storing evaluations, blobs and functions.


@dataclass
class PollEvalResult:
    value: Any
    origin: Literal["local", "cloud"]


class StoreAPI(Protocol):
    """Common calls for local and cloud cache. We assume that the API has access to the current session."""

    def poll_eval(self, key: EvalKey, deps=None) -> Union[PollEvalResult, StoreMiss]:
        ...

    def start_eval(
        self,
        key: EvalKey,
        *,
        is_experiment: bool = False,
        args: Dict[str, Any],
        deps: Dict,
        start_time: datetime,
    ) -> int:
        ...

    def resolve_eval(
        self,
        key: EvalKey,
        *,
        result: Any,
        elapsed_process_time: int,
    ) -> None:
        ...

    # def reject_eval(
    #     self, key: EvalKey, error: Exception, elapsed_process_time: int
    # ) -> None:
    #     ...

    # def invalidate(self, fn_key: CodeVertex, fn_hash=None, args_hash=None):
    #     ...

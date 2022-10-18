from dataclasses import asdict, dataclass, field, replace
from typing import (
    Any,
    Generic,
    List,
    Optional,
    Dict,
    NamedTuple,
    Protocol,
    TypeVar,
    Union,
)
import msgpack
import pickle
from hitsave.codegraph import CodeVertex
from hitsave.util import ofdict
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

logger = logging.getLogger("hitsave")


@dataclass
class EvalKey:
    """An EvalKey is a unique identifier for an evaluation"""

    fn_key: CodeVertex
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


@dataclass
class Eval(Generic[R]):
    """Evaluation that is stored in the dictionary."""

    key: EvalKey
    result: R
    args: Optional[Dict[str, Any]] = field(default=None)
    start_time: Optional[datetime] = field(default=None)
    """ time when the evaluation started  """

    elapsed_process_time: Optional[int] = field(default=None)
    """ process time elapsed in nanoseconds.  """


@dataclass
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

# [todo] use same protocol as aiocache https://github.com/aio-libs/aiocache

class EvalStore(Protocol):
    def get(self, key: EvalKey) -> Union[Eval, StoreMiss]:
        ...

    def set(self, e: Eval) -> None:
        ...

    def close(self):
        ...

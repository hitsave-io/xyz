from dataclasses import asdict, dataclass, field
import shelve
import os
import tempfile
import inspect
from typing import Any, Callable, Generic, TypeVar, overload
from hitsave.deephash import deephash, hash_function
from hitsave.codegraph import CodeVertex
import atexit
from functools import update_wrapper
from hitsave.session import Session
from hitsave.types import Eval, EvalKey, StoreMiss
import logging
from datetime import datetime
import time
from typing_extensions import ParamSpec  # needed for ≤3.9

logger = logging.getLogger("hitsave")

# https://peps.python.org/pep-0612
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class SavedFunction(Generic[P, R]):

    func: Callable[P, R]

    local_only: bool = field(default=False)  # [todo] not used yet

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        session = Session.get_current_session()
        sig = inspect.signature(self.func)
        ba = sig.bind(*args, **kwargs)
        fn_key = CodeVertex.of_object(self.func)
        fn_hash = hash_function(session.codegraph, self.func)
        args_hash = deephash(ba.arguments)
        key = EvalKey(fn_key=fn_key, fn_hash=fn_hash, args_hash=args_hash)
        r = session.store.get(key)
        if isinstance(r, StoreMiss):
            logger.info(f"No stored value for {fn_key.pp()}: {r.reason}")
            start_time = datetime.now()
            start_process_time = time.process_time_ns()
            result = self.func(*args, **kwargs)
            end_process_time = time.process_time_ns()
            e = Eval(
                key=key,
                result=result,
                args=dict(ba.arguments),
                start_time=start_time,
                elapsed_process_time=end_process_time - start_process_time,
            )
            session.store.set(e)
            logger.info(f"Saved value for {fn_key.pp()}.")
            return result
        else:
            logger.info(f"Found cached value for {fn_key.pp()}")
            return r.result


@overload
def memo(func: Callable[P, R]) -> SavedFunction[P, R]:
    ...


@overload
def memo(
    *, local_only: bool = False
) -> Callable[[Callable[P, R]], SavedFunction[P, R]]:
    ...


def memo(func=None, **kwargs):  # type: ignore
    """Memoise a function on the cloud."""
    if func == None:
        return lambda func: memo(func, **kwargs)
    if callable(func):
        g = update_wrapper(SavedFunction(func, **kwargs), func)
        return g
    raise TypeError(
        f"@{memo.__name__} requires that the given saved object {func} is callable."
    )

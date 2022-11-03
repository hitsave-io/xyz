from dataclasses import asdict, dataclass, field
import shelve
import os
import tempfile
import inspect
from typing import Any, Callable, Generic, TypeVar, overload
from hitsave.deephash import deephash
from hitsave.codegraph import Symbol, get_binding
import atexit
from functools import update_wrapper
from hitsave.session import Session
from hitsave.types import Eval, EvalKey, StoreMiss
import logging
from datetime import datetime, timezone
import time
from typing_extensions import ParamSpec  # needed for ≤3.9

logger = logging.getLogger("hitsave")

# https://peps.python.org/pep-0612
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class SavedFunction(Generic[P, R]):

    func: Callable[P, R]

    is_experiment: bool = field(default=False)
    """ An experiment is a variant of a SavedFunction which will not be deleted by the cache cleaning code. """

    local_only: bool = field(default=False)  # [todo] not used yet

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        session = Session.current()
        sig = inspect.signature(self.func)
        ba = sig.bind(*args, **kwargs)
        fn_key = Symbol.of_object(self.func)
        deps = session.fn_deps(fn_key)
        fn_hash = session.fn_hash(fn_key)
        args_hash = deephash(ba.arguments)
        key = EvalKey(fn_key=fn_key, fn_hash=fn_hash, args_hash=args_hash)
        r = session.store.poll_eval(key, deps=deps)
        if isinstance(r, StoreMiss):
            logger.info(f"No stored value for {fn_key.pp()}: {r.reason}")
            start_time = datetime.now(timezone.utc)
            start_process_time = time.process_time_ns()
            eval_id = session.store.start_eval(
                key,
                is_experiment=self.is_experiment,
                args=dict(ba.arguments),
                deps=deps,
                start_time=start_time,
            )
            result = self.func(*args, **kwargs)
            end_process_time = time.process_time_ns()
            elapsed_process_time = end_process_time - start_process_time
            session.store.resolve_eval(
                key, elapsed_process_time=elapsed_process_time, result=result
            )
            logger.info(f"Saved value for {fn_key.pp()}.")
            return result
        else:
            logger.info(f"Found cached value for {fn_key.pp()}")
            return r


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


@overload
def experiment(func: Callable[P, R]) -> SavedFunction[P, R]:
    ...


@overload
def experiment() -> Callable[[Callable[P, R]], SavedFunction[P, R]]:
    ...


def experiment(func=None, **kwargs):  # type: ignore
    """Define an experiment that saves to the cloud.

    `@experiment` behaves the same as `@memo`, the difference is that experiments are never deleted
    from the server. Also, by default experiments track the creation of artefacts such as logs and runs.
    """
    return memo(func=func, is_experiment=True, **kwargs)  # type: ignore

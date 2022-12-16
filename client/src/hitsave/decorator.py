from dataclasses import asdict, dataclass, field
import inspect
from typing import Any, Callable, Generic, List, Optional, Set, TypeVar, overload
from hitsave.console import user_info
from hitsave.codegraph import Symbol, get_binding
from functools import update_wrapper
from hitsave.session import Session
from hitsave.types import CodeChanged, Eval, EvalKey, StoreMiss
import time
from hitsave.evalstore import EvalStore
from typing_extensions import ParamSpec

from hitsave.console import logger, internal_error
from hitsave.util import datetime_now  # needed for ≤3.9


# https://peps.python.org/pep-0612
P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class Arg:
    name: Any
    value: Any
    is_default: bool
    annotation: Optional[Any]
    kind: inspect._ParameterKind
    docs: Optional[str]

    @classmethod
    def create(cls, sig: inspect.Signature, bas: inspect.BoundArguments) -> List["Arg"]:
        if bas.signature != sig:
            raise ValueError(f"Bad signature for {bas}")
        o: List[Arg] = []
        for param in sig.parameters.values():
            is_default = param.name not in bas.arguments
            value = param.default if is_default else bas.arguments[param.name]
            annotation = (
                param.annotation
                if param.annotation is not inspect.Parameter.empty
                else None
            )
            o.append(
                Arg(
                    name=param.name,
                    value=value,
                    is_default=is_default,
                    annotation=annotation,
                    kind=param.kind,
                    docs=None,  # [todo]
                )
            )
        return o


@dataclass
class SavedFunction(Generic[P, R]):
    func: Callable[P, R]

    debug_mode: bool = field(default=False)
    """ In debug mode, exceptions thrown in HitSave will not be swallowed. """

    is_experiment: bool = field(default=False)
    """ An experiment is a variant of a SavedFunction which will not be deleted by the cache cleaning code. """

    local_only: bool = field(default=False)  # [todo] not used yet
    invocation_count: int = field(default=0)
    _fn_hashes_reported: Set[str] = field(default_factory=set)

    def call_core(self, *args: P.args, **kwargs: P.kwargs) -> R:
        self.invocation_count += 1
        session = Session.current()
        sig = inspect.signature(self.func)
        ba = sig.bind(*args, **kwargs)
        args_hash = session.deephash(ba.arguments)
        pretty_args = Arg.create(sig, ba)
        fn_key = Symbol.of_object(self.func)
        deps = session.fn_deps(fn_key)
        fn_hash = session.fn_hash(fn_key)
        key = EvalKey(fn_key=fn_key, fn_hash=fn_hash, args_hash=args_hash)
        evalstore = EvalStore.current()
        result = evalstore.poll_eval(key, deps=deps, local_only=self.local_only)
        if isinstance(result, StoreMiss):
            if isinstance(result, CodeChanged):
                if fn_hash not in self._fn_hashes_reported:
                    user_info(
                        f"Dependencies changed for",
                        fn_key,
                        "\n" + result.reason,
                        highlight=False,
                    )
                    self._fn_hashes_reported.add(fn_hash)
            else:
                logger.debug(f"No stored value for {fn_key}: {result.reason}")
            start_time = datetime_now()
            start_process_time = time.process_time_ns()
            evalstore.start_eval(
                key,
                is_experiment=self.is_experiment,
                args=pretty_args,
                deps=deps,
                start_time=start_time,
                local_only=self.local_only,
            )
            # [todo] catch, log and rethrow errors raised by inner func.
            result = self.func(*args, **kwargs)
            end_process_time = time.process_time_ns()
            elapsed_process_time = end_process_time - start_process_time
            evalstore.resolve_eval(
                key,
                elapsed_process_time=elapsed_process_time,
                result=result,
                local_only=self.local_only,
            )
            logger.debug(f"Computed value for {fn_key}.")
            return result
        else:
            if self.invocation_count == 1:
                user_info(f"Found cache for", fn_key)
            else:
                logger.debug(f"Found cached value for {fn_key}.")
            return result.value

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.debug_mode:
            return self.call_core(*args, **kwargs)
        try:
            return self.call_core(*args, **kwargs)
        except Exception as e:
            internal_error(
                "Unhandled exception, falling back to decorator-less behaviour.\n", e
            )
            return self.func(*args, **kwargs)


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

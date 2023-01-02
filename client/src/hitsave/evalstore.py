from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import pickle
import tempfile
from uuid import UUID, uuid4
from blake3 import blake3
import requests
from typing import IO, Any, Dict, List, Literal, Optional, Union
from hitsave.blobstore import BlobInfo, BlobStore, get_digest_and_length
from hitsave.codegraph import Binding, BindingKind, Symbol
from hitsave.console import internal_error, user_info, tape_progress
from hitsave.types import (
    CodeChanged,
    EvalKey,
    EvalStatus,
    PollEvalResult,
    StoreMiss,
)
from hitsave.config import Config
import logging
from hitsave.cloudutils import (
    request,
    ConnectionError,
)
from contextlib import nullcontext
from hitsave.session import Session
from hitsave.util import Current, datetime_to_string
from hitsave.util.tinyorm import Schema, Table, col, transaction
from hitsave.visualize import visualize_rec
from hitsave.visualize import visualize_rec
from hitsave.console import logger
import hitsave.util.tinyorm as tinyorm

""" An eval result is stored in a few different ways:
- inline on the eval entry; this is good for things like integers and small strings.
- inline on the results table. This is good for medium-sized values that appear more frequently
- blob digest of a pickled python value. This is good for large objects.
 """


@dataclass
class Eval(Schema):
    id: UUID = col(primary=True, default_factory=uuid4)
    symbol: Symbol = col()
    binding_digest: str = col()
    args_digest: str = col()
    deps: dict[str, str] = col(encoding="json")
    status: EvalStatus = col()
    start_time: datetime = col()
    is_experiment: bool = col(default=False)
    result_digest: Optional[str] = col(default=None)
    """ BLAKE3 digest of the pickled value. """
    elapsed_process_time: Optional[bool] = col(default=None)


@dataclass
class BindingRecord(Schema):
    symbol: str = col(primary=True)
    digest: str = col(primary=True)
    diffstr: str = col()
    kind: BindingKind = col()


@dataclass
class Result(Schema):
    digest: str = col(primary=True)
    content_length: int = col()
    pickle: bytes = col()


@tinyorm.adapt.register(Symbol)
def _adapt_symb(s: Symbol) -> str:
    return str(s)


@tinyorm.restore.register(Symbol)
def _restore_sym(x: str):
    assert isinstance(x, str)
    return Symbol.of_str(x)


class LocalEvalStore:
    bindings: Table[BindingRecord]
    evals: Table[Eval]
    results: Table[Result]
    # [todo] in-mem cache EvalKey → python value.
    def __init__(self):
        self.bindings = BindingRecord.create_table("bindings")
        self.evals = Eval.create_table("evals")
        self.results = Result.create_table("results")
        logger.debug(f"Initialised local database.")

    def len_evals(self):
        return len(self.evals)

    def __len__(self):
        """Returns number of evals in the table"""
        return self.len_evals()

    def get_result(self, result_digest: str):
        r = self.results.select_one(where={Result.digest: result_digest})
        if r is not None:
            return

    def poll_eval(
        self, key: EvalKey, deps: Dict[Symbol, Binding]
    ) -> Union[PollEvalResult, StoreMiss]:
        # [todo]; in-mem caching goes here.
        symbol = str(key.fn_key)
        binding_digest = key.fn_hash
        args_digest = key.args_hash
        with transaction():

            es = self.evals.select(
                where={
                    Eval.symbol: symbol,
                    Eval.binding_digest: binding_digest,
                    Eval.args_digest: args_digest,  # [todo] refactor EvalKey
                    Eval.status: EvalStatus.resolved,  # [todo] rejected evals should reject immediately.
                }
            )
            for e in es:
                rd = e.result_digest
                if rd is None:
                    continue
                r = self.results.select_one(where=Result.digest == rd)
                if r is not None:
                    value = pickle.loads(r.pickle)
                    return PollEvalResult(value=value, origin="local")
                bs = BlobStore.current()
                if bs.has_blob(rd):
                    with bs.open_blob(rd) as f:
                        try:
                            value = pickle.load(f)
                            return PollEvalResult(value=value, origin="local")
                        except:
                            msg = f"Corrupted result for {str(key)}"
                            logger.error(msg)
                            return StoreMiss(msg)

            # find the most recent evals where the binding id doesn't match.
            x = self.evals.select_one(
                where={
                    Eval.symbol: symbol,
                    Eval.args_digest: args_digest,
                    Eval.status: EvalStatus.resolved,
                },
                order_by=Eval.start_time,
                descending=True,
            )

            if x is not None:
                assert isinstance(x.deps, dict)
                deps1 = {}
                for s, digest in x.deps.items():
                    # [todo] this should really be done by having a third table joining evals to bindings but cba
                    b = self.bindings.select_one(
                        where={
                            BindingRecord.symbol: s,
                            BindingRecord.digest: digest,
                        }
                    )
                    assert b is not None
                    if x is not None:
                        deps1[s] = b.diffstr
                # [todo] code changed should just store deps1.
                deps2 = {str(k): v.diffstr for k, v in deps.items()}
                return CodeChanged(old_deps=deps1, new_deps=deps2)

            e = self.evals.select_one(
                where={
                    Eval.symbol: symbol,
                    Eval.binding_digest: binding_digest,
                    Eval.status: EvalStatus.resolved,
                }
            )
            if e is not None:
                return StoreMiss("New arguments")
            return StoreMiss("No evaluation found")

    def start_eval(
        self,
        key: EvalKey,
        *,
        is_experiment: bool = False,
        args: Dict[str, Any],
        deps: Dict[Symbol, Binding],
        start_time: datetime,
    ) -> UUID:
        # [todo] enforce this: deps is Dict[symbol, digest]
        # note: we don't bother storing args locally.
        symbol = key.fn_key
        binding_digest = key.fn_hash
        args_digest = key.args_hash
        digests = {str(k): v.digest for k, v in deps.items()}
        with transaction():
            self.bindings.insert_many(
                [
                    BindingRecord(str(k), v.digest, v.diffstr, v.kind)
                    for k, v in deps.items()
                ],
                exist_ok=True,
            )
            if self.evals.select_one(
                where={
                    Eval.args_digest: args_digest,
                    Eval.binding_digest: binding_digest,
                    Eval.status: EvalStatus.started,
                }
            ):
                """This can happen when:
                - The app was killed before rejecting the evals. In this case; delete the row.
                  On startup we should delete any started eval rows.
                - We are running with concurrency, and the function has already been entered.
                  In which case the other threads should block / await until it's done.

                """
                raise RuntimeError(f"Eval {key} already started.")
            id = self.evals.insert_one(
                Eval(
                    symbol=symbol,
                    binding_digest=binding_digest,
                    args_digest=args_digest,
                    deps=digests,
                    result_digest=None,
                    status=EvalStatus.started,
                    start_time=start_time,
                    is_experiment=is_experiment,
                ),
                returning=Eval.id,
            )
            return id

    def resolve_eval(
        self,
        id: UUID,
        *,
        result: Union[Result, BlobInfo],
        elapsed_process_time: int,
    ):
        # [todo] fail with friendly error if the result is not picklable.
        # give a list of suggestions: try saving as a file-snapshot.
        # instructions on how to use the pickling system.
        # if the object is defined in a library, tell us and we can support it!
        # [todo] add result to in-mem cache here.
        result_digest = result.digest
        assert isinstance(id, UUID)
        with transaction():
            if isinstance(result, BlobInfo):
                assert BlobStore.current().has_blob(result.digest), "blob not found"
            elif isinstance(result, Result):
                self.results.insert_one(result, exist_ok=True)
            else:
                raise TypeError(f"{type(result)}")

            i = self.evals.update(
                {
                    Eval.status: EvalStatus.resolved,
                    Eval.result_digest: result_digest,
                    Eval.elapsed_process_time: elapsed_process_time,
                },
                where=Eval.id == id,
            )
            if i == 0:
                raise KeyError(f"Failed to find an evaluation with id {id}")

    def reject_eval(self, id: UUID, elapsed_process_time : Optional[int] = None):
        assert isinstance(id, UUID)
        with transaction():
            n = self.evals.update({
                Eval.status: EvalStatus.rejected,
                Eval.elapsed_process_time: elapsed_process_time,
            }, where = Eval.id == id)
            if n == 0:
                raise KeyError(f"Failed to find evaluation with id {id}")

    def clear(self):
        self.bindings.drop()
        self.evals.drop()
        self.results.drop()
        # [todo] clear the caches too.

    # [todo] import_eval for when you download an eval from cloud. maybe all evals should be pulled at once.


class CloudEvalStore:
    pending: Dict

    def __init__(self):
        self.pending = {}
        pass

    def request_eval(self, key: EvalKey, method: str = "GET") -> requests.Response:
        q = dict(
            fn_key=str(key.fn_key),
            fn_hash=key.fn_hash,
            args_hash=key.args_hash,
            # if poll is true, we increment a counter in the HitSave database. We use this to show you metrics about time saved etc.
            poll="true",
        )
        r = request("GET", "/eval", params=q)
        return r

    def prod(self, key: EvalKey) -> None:
        self.request_eval(key)

    def poll_eval(self, key: EvalKey, **kwargs) -> Union[PollEvalResult, StoreMiss]:
        try:
            r = self.request_eval(key)
            if r.status_code == 404:
                return StoreMiss("Not found.")
            if r.status_code == 403:
                # [todo] unauthorized
                pass
            r.raise_for_status()
        except ConnectionError as err:
            # request will already tell the user they are offline. We just fail here.
            return StoreMiss(
                f"Failed to establish a connection to {Config.current().cloud_url}."
            )
        except Exception as err:
            msg = f"Request failed: {err}"
            logger.error(msg)
            return StoreMiss(msg)
        results: list = r.json()
        for result in results:
            logger.debug(f"Found cloud eval for {key.fn_key}.")
            digest = result["content_hash"]  # [todo] will be renamed
            # [todo]; for now, blobs are always streamed, but in the future we will probably put small blobs inline.
            # we also don't store result blobs locally.
            with BlobStore.current().cloud.open_blob(digest) as tape:
                value = pickle.load(tape)
                return PollEvalResult(value, origin="cloud")
        return StoreMiss("No results.")

    def start_eval(
        self,
        key: EvalKey,
        **kwargs
        # *,
        # is_experiment: bool = False,
        # args: Dict[str, Any],
        # deps: Dict[Symbol, Binding],
        # start_time: datetime,
    ) -> Any:
        # [todo] server doesn't currently support separate start/resolve
        self.pending[key] = kwargs
        return key

    def resolve_eval(self, key: EvalKey, *, result: Any, elapsed_process_time: int):
        if not key in self.pending:
            internal_error(f"EvalKey {key} is not pending resolution")
        e = self.pending[key]
        with tempfile.SpooledTemporaryFile() as tape:
            pickle.dump(result, tape)
            tape.seek(0)
            info = BlobStore.current().add_blob(tape, label=str(key))

        args = [visualize_rec(x) for x in e.get("args", None)]
        metadata = dict(
            fn_key=str(key.fn_key),
            fn_hash=key.fn_hash,
            args_hash=key.args_hash,
            args=args,
            content_hash=info.digest,
            content_length=info.content_length,
            is_experiment=e["is_experiment"],
            start_time=datetime_to_string(e["start_time"]),
            elapsed_process_time=elapsed_process_time,
            result_json=visualize_rec(result),
        )

        try:
            r = request("PUT", f"/eval/", json=metadata)
            r.raise_for_status()
        except ConnectionError:
            # we are offline. we have already told the user this.
            return False
        except KeyboardInterrupt:
            user_info("Keyboard interrupt detected, skipping upload.")
        except Exception as err:
            # [todo] manage errors
            # they should all result in the user being given some friendly advice about
            # how they can make sure their thing is uploaded.
            logger.error(err)
        BlobStore.current().push_blob(info.digest)

    def reject_eval(self, key, **kwargs):
        logger.debug("Erroring evals not supported on server.")
        return


class EvalStore(Current):
    local: LocalEvalStore
    cloud: CloudEvalStore

    def __init__(self):
        self.local = LocalEvalStore()
        self.cloud = CloudEvalStore()

    @classmethod
    def default(cls):
        return EvalStore()

    def poll_eval(
        self, key: EvalKey, local_only=False, **kwargs
    ) -> Union[PollEvalResult, StoreMiss]:
        cfg = Config.current()
        local_only = local_only or cfg.no_cloud
        if cfg.no_local and local_only:
            return StoreMiss("Cloud and local stores are disabled.")
        if cfg.no_local:
            return self.cloud.poll_eval(key, **kwargs)
        if local_only:
            return self.local.poll_eval(key, **kwargs)

        r_local = self.local.poll_eval(key, **kwargs)
        if isinstance(r_local, StoreMiss):
            r_cloud = self.cloud.poll_eval(key, **kwargs)
            if isinstance(r_cloud, StoreMiss):
                return r_local
            else:
                # [todo] set local, just download all of the evals.
                return r_cloud
        else:
            # [todo] poll cloud anyway but don't download
            return r_local

    def start_eval(self, key, *, local_only=False, **kwargs) -> None:
        if not Config.current().no_local:
            self.local.start_eval(key, **kwargs)
        if local_only or not Config.current().no_cloud:
            self.cloud.start_eval(key, **kwargs)

    def resolve_eval(self, key, *, local_only=False, **kwargs) -> None:
        if not Config.current().no_local:
            self.local.resolve_eval(key, **kwargs)
        if local_only or not Config.current().no_cloud:
            self.cloud.resolve_eval(key, **kwargs)

    def reject_eval(self, key, *, local_only=False, **kwargs) -> None:
        if not Config.current().no_local:
            self.local.reject_eval(key, **kwargs)
        if local_only or not Config.current().no_cloud:
            self.cloud.reject_eval(key, **kwargs)

    def clear_local(self, *args, **kwargs):
        return self.local.clear(*args, **kwargs)

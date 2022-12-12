from datetime import datetime
import json
from pathlib import Path
import pickle
import tempfile
import requests
from typing import IO, Any, Dict, List, Literal, Optional, Union
from hitsave.blobstore import BlobStore, get_digest_and_length
from hitsave.codegraph import Binding, Symbol
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
from hitsave.visualize import visualize_rec
from hitsave.visualize import visualize_rec
from hitsave.console import logger


def localdb():
    return Session.current().local_db


class LocalEvalStore:
    def __init__(self):
        with localdb() as conn:
            # id autoincrements https://www.sqlite.org/faq.html#q1
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evals (
                    id INTEGER PRIMARY KEY,
                    fn_key TEXT NOT NULL,
                    fn_hash TEXT NOT NULL,
                    args_hash TEXT NOT NULL,
                    deps TEXT,
                    result BLOB,
                    status INTEGER NOT NULL,
                    start_time TEXT
                );
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bindings (
                    symbol TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    diffstr TEXT,
                    kind INTEGER,
                    PRIMARY KEY (symbol, digest)
                );
            """
            )
        logger.debug(f"Initialised local database.")

    def len_evals(self):
        with localdb() as conn:
            r = conn.execute("SELECT COUNT(*) FROM evals;")
            return r.fetchone()[0]

    def __len__(self):
        """Returns number of evals in the table"""
        return self.len_evals()

    def poll_eval(
        self, key: EvalKey, deps: Dict[Symbol, Binding]
    ) -> Union[PollEvalResult, StoreMiss]:
        with localdb() as conn:
            cur = conn.execute(
                """
                SELECT result FROM evals
                WHERE fn_key = ? AND fn_hash = ? AND args_hash = ? AND status = ?;
            """,
                (
                    str(key.fn_key),
                    key.fn_hash,
                    key.args_hash,
                    EvalStatus.resolved.value,
                ),
            )
            result = cur.fetchall()
            if len(result) != 0:
                # [todo] orderby start time.
                try:
                    value = pickle.loads(result[0][0])
                    return PollEvalResult(value=value, origin="local")
                except:
                    msg = f"Corrupted result for {str(key)}"
                    logger.error(msg)
                    return StoreMiss(msg)

            cur = conn.execute(
                """
                SELECT deps FROM evals
                WHERE fn_key = ? AND args_hash = ? AND status = ?
                ORDER BY start_time DESC;
            """,
                (
                    str(key.fn_key),
                    key.args_hash,
                    EvalStatus.resolved.value,
                ),
            )
            x = cur.fetchone()
            if x is not None:
                if deps is not None:
                    symbol_to_digest = json.loads(x[0])
                    deps1 = {}
                    for s, digest in symbol_to_digest.items():
                        # [todo] this should really be done by having a third table joining evals to deps but cba
                        x = conn.execute(
                            """SELECT diffstr FROM bindings
                            WHERE symbol = ? AND digest = ?;""",
                            (s, digest),
                        ).fetchone()
                        if x is not None:
                            deps1[s] = x[0]
                    # [todo] code changed should just store deps1.
                    deps2 = {str(k): v.diffstr for k, v in deps.items()}
                    return CodeChanged(old_deps=deps1, new_deps=deps2)
            cur = conn.execute(
                """
                SELECT deps FROM evals
                WHERE fn_key = ? AND fn_hash = ? AND status = ?
                ORDER BY start_time DESC; """,
                (
                    str(key.fn_key),
                    key.fn_hash,
                    EvalStatus.resolved.value,
                ),
            )
            x = cur.fetchone()
            if x is not None:
                return StoreMiss("New arguments.")
            return StoreMiss("No evaluation found")

    def start_eval(
        self,
        key: EvalKey,
        *,
        is_experiment: bool = False,
        args: Dict[str, Any],
        deps: Dict[Symbol, Binding],
        start_time: datetime,
    ) -> int:
        # [todo] enforce this: deps is Dict[symbol, digest]
        # note: we don't bother storing args locally.
        with localdb() as conn:
            # [todo] what to do if there is already a started eval?
            digests = {str(k): v.digest for k, v in deps.items()}
            conn.executemany(
                """
                INSERT OR IGNORE INTO bindings(symbol, digest, diffstr, kind)
                VALUES (?, ?, ?, ?); """,
                [(str(k), v.digest, v.diffstr, v.kind.value) for k, v in deps.items()],
            )
            c = conn.execute(
                """
                INSERT INTO evals
                  (fn_key, fn_hash, args_hash, status, deps, start_time)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id; """,
                (
                    str(key.fn_key),
                    key.fn_hash,
                    key.args_hash,
                    EvalStatus.started.value,
                    json.dumps(digests),
                    datetime_to_string(start_time),
                ),
            )
            (id,) = c.fetchone()
            return id

    def resolve_eval(self, key: EvalKey, *, result: Any, elapsed_process_time: int):
        # [todo] fail with friendly error if the result is not picklable.
        # give a list of suggestions: try saving as a file-snapshot.
        # instructions on how to use the pickling system.
        # if the object is defined in a library, tell us and we can support it!
        with localdb() as conn:
            conn.execute(
                """
                UPDATE evals
                SET status = ?, result = ?
                WHERE fn_key = ? AND fn_hash = ? AND args_hash = ? AND status = ?; """,
                (
                    EvalStatus.resolved.value,
                    pickle.dumps(result),  # [todo] should go to blob
                    str(key.fn_key),
                    key.fn_hash,
                    key.args_hash,
                    EvalStatus.started.value,
                ),
            )
            # [todo], if this didn't update anything it means that multiple processes or threads evaluated at the same time!

    def reject_eval(self, key: EvalKey):
        raise NotImplementedError()

    def clear(self):
        tables = ["evals", "bindings"]
        with localdb() as conn:
            for table in tables:
                conn.execute(f"DROP TABLE {table};")
                logger.debug("Dropped local ", table)

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

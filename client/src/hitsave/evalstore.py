from datetime import datetime
import json
from pathlib import Path
import pickle
import tempfile
import requests
from typing import IO, Any, Dict, List, Literal, Optional, Union
from hitsave.blobstore import BlobStore, get_digest_and_length
from hitsave.codegraph import Binding, Symbol
from hitsave.types import (
    CodeChanged,
    EvalKey,
    EvalStatus,
    PollEvalResult,
    StoreMiss,
    StoreAPI,
)
from hitsave.config import Config
from diskcache import Cache
import os.path
import logging
from blake3 import blake3
import sqlite3
from hitsave.cloudutils import (
    request,
    read_header,
    create_header,
    encode_hitsavemsg,
    ConnectionError,
)
from hitsave.session import Session
from hitsave.util import Current, datetime_to_string
from hitsave.visualize import visualize_rec
from hitsave.visualize import visualize_rec

logger = logging.getLogger("hitsave")


def localdb():
    return Session.current().local_db


class UselessEvalStore:
    def __init__(self):
        pass

    def poll_eval(self, *args, **kwargs):
        return StoreMiss("Disabled.")

    def start_eval(self, *args, **kwargs):
        return 0

    def resolve_eval(self, *args, **kwargs):
        pass

    def reject_eval(self, *args, **kwargs):
        pass

    def clear(self):
        pass

    def __len__(self):
        return 0


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
        with localdb() as conn:
            conn.execute(
                """
                UPDATE evals
                SET status = ?, result = ?
                WHERE fn_key = ? AND fn_hash = ? AND args_hash = ? AND status = ?; """,
                (
                    EvalStatus.resolved.value,
                    pickle.dumps(result),
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
        tables = [("evals",), ("bindings",)]
        with localdb() as conn:
            conn.executemany(
                """
              DELETE FROM ?;
            """,
                tables,
            )
            conn.executemany("""DROP TABLE ?;""", tables)
            logger.info(f"Dropped tables {tables}")

    def __len__(self):
        return len(self._store)  # type: ignore

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
            logger.debug(f"Found cloud eval for {key.fn_key.pp()}.")
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
        assert key in self.pending, f"{key} is not pending."
        e = self.pending[key]
        with tempfile.SpooledTemporaryFile() as tape:
            pickle.dump(result, tape)
            tape.seek(0)
            digest, content_length = get_digest_and_length(tape)
            tape.seek(0)
            args = e.get("args", None)
            if args is not None:
                args = {k: visualize_rec(v) for k, v in args.items()}
                # [todo] if an arg is too big, we blobify it and replace with {__kind__: blob, ...}
            payload = encode_hitsavemsg(
                dict(
                    fn_key=str(key.fn_key),
                    fn_hash=key.fn_hash,
                    args_hash=key.args_hash,
                    args=args,
                    content_hash=digest,
                    content_length=content_length,
                    is_experiment=e["is_experiment"],
                    start_time=datetime_to_string(e["start_time"]),
                    elapsed_process_time=elapsed_process_time,
                    result_json=visualize_rec(result),
                ),
                tape,
            )
            try:
                r = request("PUT", f"/eval/", data=payload)
                r.raise_for_status()
            except ConnectionError:
                # we are offline. we have already told the user this.
                return False
            except Exception as err:
                # [todo] manage errors
                # they should all result in the user being given some friendly advice about
                # how they can make sure their thing is uploaded.
                logger.error(err)

    def reject_eval(self, key, **kwargs):
        logger.debug("Erroring evals not supported on server.")
        return


class EvalStore(Current):
    local: Union[LocalEvalStore, UselessEvalStore]
    cloud: Union[CloudEvalStore, UselessEvalStore]

    def __init__(self):
        cfg = Config.current()
        self.local = LocalEvalStore() if not cfg.no_local else UselessEvalStore()
        self.cloud = CloudEvalStore() if not cfg.no_cloud else UselessEvalStore()

    @classmethod
    def default(cls):
        return EvalStore()

    def poll_eval(self, key, **kwargs):
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

    def start_eval(self, key, **kwargs):
        self.local.start_eval(key, **kwargs)
        self.cloud.start_eval(key, **kwargs)

    def resolve_eval(self, key, **kwargs):
        self.local.resolve_eval(key, **kwargs)
        self.cloud.resolve_eval(key, **kwargs)

    def reject_eval(self, key, **kwargs):
        self.local.reject_eval(key, **kwargs)
        self.cloud.reject_eval(key, **kwargs)

    # [todo] clear
    # [todo]

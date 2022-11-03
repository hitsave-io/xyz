from datetime import datetime
import json
import pickle
from typing import Any, Dict, List, Optional, Union
from hitsave.types import (
    CodeChanged,
    EvalKey,
    EvalStatus,
    StoreMiss,
    StoreAPI,
)
from hitsave.config import Config
from diskcache import Cache
import os.path
import logging
import sqlite3

logger = logging.getLogger("hitsave")


class LocalStore(StoreAPI):
    store_path: str
    conn: sqlite3.Connection

    def __init__(self, store_dir=Config.current().local_cache_dir):
        self.store_path = os.path.join(store_dir, "localstore.db")
        self.conn = sqlite3.connect(self.store_path)
        with self.conn:

            # id autoincrements https://www.sqlite.org/faq.html#q1
            self.conn.execute(
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
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fns (
                    fn_key TEXT NOT NULL,
                    fn_hash TEXT NOT NULL,
                    code TEXT,
                    PRIMARY KEY (fn_key, fn_hash)
                );
            """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS blobs (
                    digest TEXT PRIMARY KEY,
                    label TEXT,
                    length INTEGER NOT NULL
                );
            """
            )
        logger.info(f"Created local database at {self.store_path}")

    def close(self):
        self.conn.close()

    def poll_eval(self, key: EvalKey, deps) -> Union[Any, StoreMiss]:
        with self.conn:
            cur = self.conn.execute(
                """
                SELECT result FROM evals WHERE fn_key = ? AND fn_hash = ? AND args_hash = ? AND status = ?;
            """,
                (
                    str(key.fn_key),
                    key.fn_hash,
                    key.args_hash,
                    EvalStatus.resolved.value,
                ),
            )
            evs = cur.fetchall()
            if len(evs) != 0:
                # [todo] orderby start time.
                return evs[0]

            cur = self.conn.execute(
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
                    deps1 = json.loads(x[0])
                    deps2 = deps
                    return CodeChanged(old_deps=deps1, new_deps=deps2)

            return StoreMiss("No evaluation found")

    def start_eval(
        self,
        key: EvalKey,
        *,
        is_experiment: bool = False,
        args: Dict[str, Any],
        deps: Dict[str, str],
        start_time: datetime,
    ) -> int:
        # note: we don't bother storing args locally.
        with self.conn:
            # [todo] what to do if there is already a started eval?
            c = self.conn.execute(
                """
                INSERT INTO evals
                  (fn_key, fn_hash, args_hash, status, deps, start_time)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id;
                """,
                (
                    str(key.fn_key),
                    key.fn_hash,
                    key.args_hash,
                    EvalStatus.started.value,
                    json.dumps(deps),
                    start_time.isoformat(),
                ),
            )
            (id,) = c.fetchone()
            return id

    def resolve_eval(self, key: EvalKey, *, result: Any, elapsed_process_time: int):
        with self.conn:
            self.conn.execute(
                """
                UPDATE evals
                SET status = ?, result = ?
                WHERE fn_key = ? AND fn_hash = ? AND args_hash = ? AND status = ?;
            """,
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
        raise

    def clear(self):
        with self.conn:
            self.conn.executemany(
                """
              DELETE FROM ?;
            """,
                [("blobs",), ("evals",), ("fns",)],
            )
            # [todo] return COUNT(*)?

    def __len__(self):
        return len(self._store)  # type: ignore

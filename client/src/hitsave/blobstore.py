from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import IO, Optional, Tuple, Union
from hitsave.config import Config, no_cloud, no_local
from hitsave.console import tape_progress, user_info
from hitsave.session import Session
from hitsave.util import (
    Current,
    chunked_read,
    datetime_to_string,
    human_size,
    datetime_now,
)
from blake3 import blake3
from stat import S_IREAD, S_IRGRP
import tempfile
from hitsave.console import logger, internal_error
from hitsave.cloudutils import request, read_header, create_header, encode_hitsavemsg

""" This file contains everything to do with storing and retrieving blobs locally and on the cloud. """


@dataclass
class BlobInfo:
    digest: str
    content_length: int


class BlobStatus(Enum):
    to_push = 0
    synced = 1
    deleted = 2


def get_digest_and_length(tape: IO[bytes]) -> Tuple[str, int]:
    content_length = 0
    h = blake3()
    for data in chunked_read(tape):
        content_length += len(data)
        h.update(data)
    digest = h.hexdigest()
    return (digest, content_length)


def localdb():
    return Session.current().local_db


class LocalBlobStore:
    """Everything to do with storing blobs locally.

    We don't do anything with connecting to the local blobs tracking db.
    """

    def __init__(self):
        self.local_cache_dir = Config.current().local_cache_dir

    def iter_blobs(self):
        """Iterate all of the digests of the blobs that exist on disk."""
        p = self.local_cache_dir / "blobs"
        for bp in p.iterdir():
            if bp.is_file():
                digest = bp.name
                yield digest

    def local_file_cache_path(self, digest: str):
        """Gets the place where the blob would be stored. Note that this doesn't guarantee existence."""
        p = self.local_cache_dir
        return p / "blobs" / digest

    def has_blob(self, digest: str) -> bool:
        """Checks whether the blob exists __locally__."""
        return self.local_file_cache_path(digest).exists()

    def delete_blob(self, digest):
        """Deletes the given blob from the local cache.

        Note that some directories etc may symlink to this blob, so you should do this with care.
        """
        p = self.local_file_cache_path(digest)
        if p.exists():
            p.unlink()
            logger.debug(f"Deleted local blob {digest}")

    def open_blob(self, digest: str, **kwargs) -> IO:
        """Opens the blob. You are responsible for closing it.

        Will throw FileNotFoundError if the blob doesn't exist.
        """
        if not self.has_blob(digest):
            raise FileNotFoundError(f"No blob {digest}")
        return open(self.local_file_cache_path(digest), mode="rb", **kwargs)

    def __len__(self):
        with localdb() as conn:
            c = conn.execute("SELECT COUNT(*) FROM blobs;")
            return c.fetchone()[0]

    def add_blob(
        self,
        tape: IO[bytes],
        *,
        digest: Optional[str] = None,
        content_length: Optional[int] = None,
        label: Optional[str] = None,
    ) -> BlobInfo:
        """Saves a blob to the local store.

        If digest and content_length is given, it is trusted.
        """
        if digest is None or content_length is None:
            tape.seek(0)
            digest, content_length = get_digest_and_length(tape)
        tape.seek(0)
        if not self.has_blob(digest):
            cp = self.local_file_cache_path(digest)
            # [todo] exclusive file lock.
            with open(cp, "wb") as c:
                for data in chunked_read(tape):
                    c.write(data)
            # blobs are read only.
            # ref: https://stackoverflow.com/a/28492823/352201
            cp.chmod(S_IREAD | S_IRGRP)
            # [todo] what about S_IROTH?
        return BlobInfo(digest, content_length)


class CloudBlobStore:
    """Methods for getting blobs from the cloud."""

    def __init__(self):
        pass

    def has_blob(self, digest: str) -> bool:
        """Returns true if the blob exists on the cloud.

        If disconnected raises a ConnectionError.
        """
        r = request("HEAD", f"/blob/{digest}")
        return r.status_code // 100 == 2

    def get_content_length(self, digest: str) -> Optional[int]:
        r = request("HEAD", f"/blob/{digest}")
        if r.status_code == 404:
            return None
        # HEAD should never return a body
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/HEAD
        assert r.status_code == 204
        if "Content-Length" not in r.headers:
            return None
        else:
            return int(r.headers["Content-Length"])

    def add_blob(
        self,
        tape: IO[bytes],
        digest: Optional[str] = None,
        content_length: Optional[int] = None,
        label=None,
    ) -> BlobInfo:
        """Upload the blob to the cloud.

        If the blob is already present on the cloud, the blob info is returned.
        If digest and content_length are given, they are trusted.

        Raises:
            ConnectionError: We are not connected to the cloud.
        """
        if digest is None or content_length is None:
            tape.seek(0)
            digest, content_length = get_digest_and_length(tape)
        if self.has_blob(digest):
            logger.debug(f"Blob is already uploaded. {digest}")
            return BlobInfo(digest, content_length)
        tape.seek(0)
        mdata = {
            "content_hash": digest,
            "content_length": content_length,
        }
        if label is not None:
            mdata["label"] = label
        pp_label = label or "unlabelled file"
        with tape_progress(
            tape,
            content_length,
            message=f"Uploading {pp_label} ({human_size(content_length)}) {digest}.",
            description="Uploading",
        ) as tape:
            msg = encode_hitsavemsg(mdata, tape)
            r = request("PUT", "/blob", data=msg)
        r.raise_for_status()
        if label is not None:
            logger.debug(f"Uploaded {pp_label} {digest}.")
        return BlobInfo(digest, content_length)

    def open_blob(self, digest: str) -> IO[bytes]:
        """Downloads the given blob to a temporary file.

        This will always cause a download.

        Raises:
            FileNotFoundError: The blob does not exist on the cloud.
            ConectionError: We are not connected to the cloud.
        """
        if not self.has_blob(digest):
            raise FileNotFoundError(f"No blob found {digest}")
        logger.debug(f"Downloading file {digest}.")
        r = request("GET", f"/blob/{digest}")
        content_length = r.headers.get("Content-Length", None)
        if content_length is not None:
            content_length = int(content_length)
        tape = tempfile.SpooledTemporaryFile()
        with tape_progress(
            tape,
            total=content_length,
            message=f"Downloading {digest}",
            description="Downloading",
        ) as tape:
            for chunk in r.iter_content(chunk_size=2**20):
                tape.write(chunk)
        tape.seek(0)
        return tape


class BlobStore(Current):
    """Combined local and cloud blob storage system.

    We maintain a local db of the status of the blobs to track cache management.
    """

    def __init__(self):
        self.local = LocalBlobStore()
        self.cloud = CloudBlobStore()
        with localdb() as conn:
            conn.execute(
                """
                    CREATE TABLE IF NOT EXISTS blobs (
                        digest TEXT PRIMARY KEY NOT NULL,
                        length INTEGER NOT NULL,
                        label TEXT,
                        status INTEGER,
                        accesses INTEGER,
                        last_accessed TEXT,
                        created TEXT
                    );
                """
            )

    @classmethod
    def default(cls):
        return BlobStore()

    def touch(self, digest: str):
        """Tell the local db that the blob has been accessed."""
        time = datetime_to_string(datetime_now())
        with localdb() as conn:
            conn.execute(
                """
                UPDATE blobs
                SET last_accessed = ?, accesses = accesses + 1
                WHERE digest = ?;
            """,
                (time, digest),
            )

    def open_blob(self, digest: str) -> IO[bytes]:
        """Returns a readable IO stream of the blob with the given digest.
        If the blob is present in the local cache, this will be used, otherwise we download from the cloud.

        Raises:
            FileNotFoundError: If the blob is not present locally or on cloud.
        """
        self.touch(digest)
        if no_local():
            return self.cloud.open_blob(digest=digest)
        if no_cloud():
            return self.local.open_blob(digest=digest)
        try:
            return self.local.open_blob(digest=digest)
        except FileNotFoundError:
            pass
        if no_cloud():
            raise FileNotFoundError(
                f"Blob {digest[0:10]} not found locally and HITSAVE_NO_CLOUD is enabled."
            )
        tape = self.cloud.open_blob(digest=digest)
        info = self.local.add_blob(tape)
        if info.digest != digest:
            internal_error(f"Corrupted digest of cloud file {digest}")
        tape.seek(0)
        self.touch(digest)
        return tape

    def add_blob(self, item: Union[str, bytes, IO[bytes]], **kwargs) -> BlobInfo:
        """Creates a new binary blob from the given readable, seekable ``tape`` IO stream."""
        if isinstance(item, str):
            item = item.encode("utf-8")
        if isinstance(item, bytes):
            with io.BytesIO(item) as tape:
                return self._add_blob_core(tape, **kwargs)
        else:
            return self._add_blob_core(item, **kwargs)

    def _add_blob_core(
        self, tape: IO[bytes], digest=None, content_length=None, label=None
    ) -> BlobInfo:
        """Creates a new binary blob from the given readable, seekable ``tape`` IO stream."""
        if no_local():
            return self.cloud.add_blob(
                tape, digest=digest, content_length=content_length, label=label
            )
        if no_cloud():
            return self.local.add_blob(
                tape, digest=digest, content_length=content_length, label=label
            )
        with localdb() as conn:
            time = datetime_to_string(datetime_now())
            info = self.local.add_blob(
                tape, digest=digest, content_length=content_length
            )
            digest = info.digest
            x = conn.execute(
                """SELECT status FROM blobs WHERE digest = ?""", (digest,)
            ).fetchone()
            status: Optional[BlobStatus] = None if x is None else BlobStatus(x[0])
            if status == BlobStatus.deleted:
                # undelete the blob in the local table.
                conn.execute(
                    """UPDATE blobs SET status = ? WHERE digest = ?""",
                    (BlobStatus.to_push.value, digest),
                )
                return info
            if status == BlobStatus.synced or status == BlobStatus.to_push:
                logger.debug(f"Blob {digest[:10]} already present in local blob table.")
                return info
            if x is None:
                conn.execute(
                    """
                INSERT INTO blobs(digest, length, label, status, accesses, last_accessed, created)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                    (
                        info.digest,
                        info.content_length,
                        label,
                        BlobStatus.to_push.value,
                        0,
                        time,
                        time,
                    ),
                )
        return info

    def has_blob(self, digest) -> bool:
        """Returns true if the digest is present either locally or on the cloud.
        If this returns true then you can safely call ``open_blob(digest)`` or ``pull_blob(digest)`` without raising a FileNotFoundError.
        """
        if no_local():
            return self.cloud.has_blob(digest)
        if no_cloud():
            return self.local.has_blob(digest)
        return self.local.has_blob(digest) or self.cloud.has_blob(digest)

    def pull_blob(self, digest) -> bool:
        """If needed, downloads the blob from the server. Raises a blobnotfound if not present.

        Returns true if a download occurred."""
        if no_cloud() or no_local():
            logger.warning(
                "Refusing to pull blob because NO_CLOUD or NO_LOCAL flag is set."
            )
            return False
        if self.local.has_blob(digest):
            logger.debug(
                f"Not pulling blob {digest[:10]} since already present locally."
            )
            return False
        with self.cloud.open_blob(digest) as tape:
            # [todo] progress bar goes here.
            info = self.local.add_blob(tape)
            if info.digest != digest:
                internal_error(f"Corrupted cloud blob {digest[:10]}")
            logger.debug(f"Pulled blob {digest}")
        # [todo] update blobs table.
        return True

    def push_blob(self, digest) -> bool:
        """If needed, pushes the blob to the cloud server.
        Return True if an upload took place."""
        if no_cloud() or no_local():
            logger.warning(
                "Refusing to push blob because NO_CLOUD or NO_LOCAL flag is set."
            )
            return False
        if self.cloud.has_blob(digest):
            return False
        with self.local.open_blob(digest) as tape:
            # [todo] progress bar logging goes here.
            info = self.cloud.add_blob(tape)
            if digest != info.digest:
                internal_error(f"Corrupted local blob {digest[:10]}")
            logger.debug(f"Pushed blob {digest}")
        with localdb() as conn:
            conn.execute(
                """UPDATE blobs SET status = ? WHERE digest = ?""",
                (
                    BlobStatus.synced.value,
                    digest,
                ),
            )
        return True

    def push_blobs(self):
        """Pushes all blobs that need pushing."""
        with localdb() as conn:
            digests = conn.execute(
                """ SELECT digest from blobs WHERE status = ? """,
                (BlobStatus.to_push.value,),
            ).fetchall()
        for (digest,) in digests:
            self.push_blob(digest)
        raise NotImplementedError()

    def local_file_cache_path(self, digest) -> Path:
        """Path to the local, readonly cached file.

        Note that the file does not necessarily exist.
        """
        return self.local.local_file_cache_path(digest)

    def restore(self, digest: str) -> Path:
        """Pulls the blob with the given digest and returns a path to it."""
        self.pull_blob(digest)
        return self.local.local_file_cache_path(digest)

    def clear_local(self):
        """Removes all entries from the blobs table."""
        with localdb() as conn:
            conn.execute("DROP TABLE blobs;")
            logger.debug("Dropped local blobs table.")

    def prune_local(self):
        """Removes all local blobs that are not present in the blobs table."""
        ok_digests = set()
        with localdb() as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='blobs';"
            )
            t = cur.fetchone()
            if t:
                cur = conn.execute("SELECT digest FROM blobs;")
                ok_digests = set(d for (d,) in cur)
        delete_me = set()
        for digest in self.local.iter_blobs():
            if digest not in ok_digests:
                delete_me.add(digest)
        user_info("Deleting", len(delete_me), "local blobs...")
        for digest in delete_me:
            self.local.delete_blob(digest)
        user_info("Deleted.")


def restore(digest: str) -> Path:
    """Pull and restore the blob with the given digest.

    Raises:
      FileNotFoundError: if not a known digest.
    """
    # [todo] assert this looks like a hex digest.
    return BlobStore.current().restore(digest)

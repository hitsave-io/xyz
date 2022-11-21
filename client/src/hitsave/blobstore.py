from dataclasses import dataclass
import datetime
from enum import Enum
from pathlib import Path
from typing import IO, Optional, Tuple
import warnings
from hitsave.config import Config, no_cloud, no_local
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
import logging
import tempfile
from hitsave.cloudutils import request, read_header, create_header, encode_hitsavemsg

""" This file contains everything to do with storing and retrieving blobs locally and on the cloud. """

logger = logging.getLogger("hitsave")


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


class UselessBlobStore:
    kind: str

    def __init__(self, kind):
        self.kind = kind

    def has_blob(self, digest):
        return False

    def open_blob(self, digest) -> IO[bytes]:
        raise FileNotFoundError(f"{self.kind} store is deactivated.")

    def add_blob(self, tape, *args, **kwargs):
        return None


class LocalBlobStore:
    """Everything to do with storing blobs locally.

    We don't do anything with connecting to the local blobs tracking db.
    """

    def __init__(self):
        self.local_cache_dir = Config.current().local_cache_dir

    def local_file_cache_path(self, digest: str):
        """Gets the place where the blob would be stored. Note that this doesn't guarantee existence."""
        p = self.local_cache_dir
        return p / "blobs" / digest

    def has_blob(self, digest: str) -> bool:
        """Checks whether the blob exists __locally__."""
        return self.local_file_cache_path(digest).exists()

    def delete_blob(self, digest):
        """Deletes the given blob from the local cache.
        Note that some directories etc may symlink to this blob, so we should do this with care.
        """
        raise NotImplementedError()

    def open_blob(self, digest: str, **kwargs) -> IO:
        """Opens the blob. You are responsible for closing it.

        Can throw if the blob doesn't exist.
        [todo] will download the blob if not present locally.
        """
        if not self.has_blob(digest):
            raise FileNotFoundError(f"No blob {digest}")
        return open(self.local_file_cache_path(digest), mode="rb", **kwargs)

    def add_blob(
        self,
        tape: IO[bytes],
        *,
        digest=None,
        content_length=None,
    ) -> BlobInfo:
        """Given a spoolable, readable bytestream. saves it.
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
            cp.chmod(S_IREAD | S_IRGRP)  # [todo] what about S_IROTH?
            # [todo] queue blob for upload.
            # [todo] have a 'blobs' table that tracks upload status.
        return BlobInfo(digest, content_length)


class CloudBlobStore:
    """Methods for getting blobs from the cloud."""

    def __init__(self):
        # [todo] get connection from session.
        pass

    def has_blob(self, digest: str) -> bool:
        r = request("HEAD", f"/blob/{digest}")
        return r.status_code == 200

    def add_blob(
        self,
        tape: IO[bytes],
        digest: Optional[str] = None,
        content_length: Optional[int] = None,
        label=None,
    ) -> BlobInfo:
        """Note: this always __uploads__ the blob."""
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
        msg = encode_hitsavemsg(mdata, tape)
        pp_label = label or "unlabelled file"
        if content_length > 2**20:
            logger.info(f"Uploading {pp_label} ({human_size(content_length)}).")
        # [todo] cute progress bar.
        r = request("PUT", "/blob", data=msg)
        r.raise_for_status()
        if label is not None:
            logger.debug(f"Uploaded {pp_label} ({human_size(content_length)}).")
        return BlobInfo(digest, content_length)

    def open_blob(self, digest: str):
        """note: this __always__ downloads the blob."""
        if not self.has_blob(digest):
            raise FileNotFoundError(f"No blob found {digest}")
        logger.debug(f"Downloading file {digest}.")
        r = request("GET", f"/blob/{digest}")
        tape = tempfile.SpooledTemporaryFile()
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
        """Tell the db that the blob has been accessed."""
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

        Raises a ``FileNotFoundError`` if the blob is not present locally or on cloud."""
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
        assert info.digest != digest, f"Corrupted digest of cloud file {digest}"
        tape.seek(0)
        self.touch(digest)
        return tape

    def add_blob(
        self, tape: IO[bytes], digest=None, content_length=None, label=None
    ) -> BlobInfo:
        """Creates a new binary blob from the given readable, seekable ``tape`` IO stream."""
        assert tape.seekable()
        assert tape.readable()
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
                conn.execute(
                    """UPDATE blobs SET status = ? WHERE digest = ?""",
                    (BlobStatus.to_push.value, digest),
                )
                return info
            if status == BlobStatus.synced or status == BlobStatus.to_push:
                logger.debug(f"Blob {digest[:10]} already present in local blob table.")
                return info
            # [todo] check if already in table first.
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
            # [todo] fancy progress bar goes here.
            info = self.local.add_blob(tape)
            assert info.digest == digest, f"Corrupted cloud blob {digest[:10]}"
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
            # [todo] fancy progress bar logging goes here.
            info = self.cloud.add_blob(tape)
            assert info.digest == digest, f"Corrupted local blob {digest[:10]}"
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
                """
            SELECT digest from blobs
            WHERE status = ?
            """,
                (BlobStatus.to_push.value,),
            ).fetchall()
        for (digest,) in digests:
            self.push_blob(digest)
        raise NotImplementedError()

    def local_file_cache_path(self, digest) -> Path:
        return self.local.local_file_cache_path(digest)

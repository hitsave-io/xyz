from dataclasses import dataclass
import datetime
from pathlib import Path
from typing import IO, Optional, Tuple
from hitsave.config import Config
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

    def local_file_cache_path(self, digest: str):
        """Gets the place where the blob would be stored. Note that this doesn't guarantee existence."""
        p = self.local_cache_dir
        return p / "blobs" / digest

    def has_blob(self, digest: str) -> bool:
        """Checks whether the blob exists __locally__."""
        return self.local_file_cache_path(digest).exists()

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
        # [todo] move this to cloud store.
        mdata = {
            "content_hash": digest,
            "content_length": content_length,
        }
        if label is not None:
            mdata["label"] = label
        msg = encode_hitsavemsg(mdata, tape)
        r = request("PUT", "/blob", data=msg)
        r.raise_for_status()
        if label is not None:
            logger.debug(f"Uploaded {label} ({human_size(content_length)}).")
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
    """Combined local and cloud blob storage system."""

    def __init__(self):
        self.local = LocalBlobStore()
        self.cloud = CloudBlobStore()
        with localdb() as conn:
            conn.execute(
                """
                    CREATE TABLE IF NOT EXISTS blobs (
                        digest TEXT NOT NULL,
                        length INTEGER NOT NULL,
                        label TEXT,
                        should_upload INTEGER,
                        accesses INTEGER,
                        last_accessed TEXT,
                        created TEXT,
                        PRIMARY KEY digest
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
        try:
            return self.local.open_blob(digest=digest)
        except FileNotFoundError:
            pass
        tape = self.cloud.open_blob(digest=digest)
        info = self.local.add_blob(tape)
        assert info.digest != digest, f"Corrupted digest of cloud file {digest}"
        tape.seek(0)
        self.touch(digest)
        return tape

    def add_blob(self, tape, digest=None, content_length=None, label=None) -> BlobInfo:
        info = self.local.add_blob(tape, digest=digest, content_length=content_length)
        time = datetime_to_string(datetime_now())
        with localdb() as conn:
            conn.execute(
                """
            INSERT OR IGNORE INTO blobs(digest, length, label, should_upload, accesses, last_accessed, created)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
                (
                    info.digest,
                    info.content_length,
                    label,
                    True,
                    0,
                    time,
                    time,
                ),
            )
        return info
        # [todo] have a flag on upload policy. There are 3 options:
        # 1. eager uploading, block until uploaded
        # 2. background uploading, start uploading immediately but on a bg thread in a queue.
        # 3. no uploading, the user has to trigger an upload with `hitsave blob upload`

        # note that local also stores a status flag to determine when something is in the 'upload queue'.

    def purge(self):
        """delete files that are not registered blobs."""

    def has_blob(self, digest) -> bool:
        return self.local.has_blob(digest) or self.cloud.has_blob(digest)

    def pull_blob(self, digest) -> bool:
        """If needed, downloads the blob from the server. Raises a blobnotfound if not present.

        Returns true if a download occurred."""
        if self.local.has_blob(digest):
            return False
        with self.cloud.open_blob(digest) as tape:
            info = self.local.add_blob(tape)
            assert info.digest == digest, f"Corrupted cloud blob {digest}"
            logger.debug(f"Pulled blob {digest}")
        with localdb() as conn:
            conn.execute("""""", (digest,))
        return True

    def push_blob(self, digest) -> bool:
        """If needed, pushes the blob to the cloud server.
        Return True if an upload took place."""
        if self.cloud.has_blob(digest):
            return False
        with self.local.open_blob(digest) as tape:
            info = self.cloud.add_blob(tape)
            assert info.digest == digest, f"Corrupted local blob {digest}"
            logger.debug(f"Pushed blob {digest}")
        with localdb() as conn:
            conn.execute(
                """UPDATE blobs SET should_upload = 0 WHERE digest = ?""", (digest,)
            )
        return True

    def push_blobs(self):
        """Pushes all blobs that need pushing."""
        with localdb() as conn:
            digests = conn.execute(
                """
            SELECT digest from blobs
            WHERE should_upload
            """
            ).fetchall()
        for (digest,) in digests:
            self.push_blob(digest)
        raise NotImplementedError()

    def pull_blobs(self):
        raise NotImplementedError()

    def local_file_cache_path(self, digest) -> Path:
        return self.local.local_file_cache_path(digest)

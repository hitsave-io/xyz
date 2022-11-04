from dataclasses import dataclass
from pathlib import Path
from typing import IO, Optional
from hitsave.config import Config
from hitsave.session import Session
from hitsave.util import Current, chunked_read, human_size
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


def get_blob_info(tape: IO[bytes]) -> BlobInfo:
    content_length = 0
    h = blake3()
    for data in chunked_read(tape):
        content_length += len(data)
        h.update(data)
    digest = h.hexdigest()
    return BlobInfo(digest, content_length)


def localdb():
    return Session.current().local_db


class LocalBlobStore:
    def __init__(self):
        self.local_cache_dir = Config.current().local_cache_dir
        pass

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
        blob_info: Optional[BlobInfo] = None,
    ) -> BlobInfo:
        """Given a spoolable, readable bytestream. saves it.
        If blob_info is given, it is trusted that the digest of the tape is the same as that of blob_info.
        """
        if blob_info is None:
            tape.seek(0)
            blob_info = get_blob_info(tape)
        tape.seek(0)
        if not self.has_blob(blob_info.digest):
            cp = self.local_file_cache_path(blob_info.digest)
            # [todo] exclusive file lock.
            with open(cp, "wb") as c:
                for data in chunked_read(tape):
                    c.write(data)
            # blobs are read only.
            # ref: https://stackoverflow.com/a/28492823/352201
            cp.chmod(S_IREAD | S_IRGRP)  # [todo] what about S_IROTH?
            # [todo] queue blob for upload.
            # [todo] have a 'blobs' table that tracks upload status.
        return blob_info


class CloudBlobStore:
    """Methods for getting blobs from the cloud."""

    def __init__(self):
        # [todo] get connection from session.
        pass

    def has_blob(self, digest: str) -> bool:
        r = request("HEAD", f"/blob/{digest}")
        return r.status_code == 200

    def add_blob(
        self, tape: IO[bytes], blob_info: Optional[BlobInfo] = None, label=None
    ) -> BlobInfo:
        """Note: this always __uploads__ the blob."""
        if blob_info is None:
            tape.seek(0)
            blob_info = get_blob_info(tape)
        if self.has_blob(blob_info.digest):
            logger.debug(f"Blob is already uploaded. {blob_info.digest}")
            return blob_info
        tape.seek(0)
        # [todo] move this to cloud store.
        mdata = {
            "content_hash": blob_info.digest,
            "content_length": blob_info.content_length,
        }
        if label is not None:
            mdata["label"] = label
        msg = encode_hitsavemsg(mdata, tape)
        r = request("PUT", "/blob", data=msg)
        r.raise_for_status()
        if label is not None:
            logger.debug(f"Uploaded {label} ({human_size(blob_info.content_length)}).")
        return blob_info

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

    @classmethod
    def default(cls):
        return BlobStore()

    def open_blob(self, digest: str) -> IO[bytes]:
        try:
            return self.local.open_blob(digest=digest)
        except FileNotFoundError:
            pass
        tape = self.cloud.open_blob(digest=digest)
        info = self.local.add_blob(tape)
        assert info.digest != digest, f"Corrupted digest of cloud file {digest}"
        tape.seek(0)
        return tape

    def add_blob(self, tape, blob_info: Optional[BlobInfo] = None) -> BlobInfo:
        return self.local.add_blob(tape, blob_info)
        # [todo] have a flag on upload policy. There are 3 options:
        # 1. eager uploading, block until uploaded
        # 2. background uploading, start uploading immediately but on a bg thread in a queue.
        # 3. no uploading, the user has to trigger an upload with `hitsave blob upload`

        # note that local also stores a status flag to determine when something is in the 'upload queue'.

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
        return True

    def push_blobs(self):
        """Pushes all blobs that need pushing."""
        raise NotImplementedError()

    def pull_blobs(self):
        raise NotImplementedError()

    def local_file_cache_path(self, digest) -> Path:
        return self.local.local_file_cache_path(digest)

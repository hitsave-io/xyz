from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from genericpath import isfile
from io import BufferedReader
from typing import Any, List, Optional, Union
from hitsave.config import Config
import os.path
from blake3 import blake3
import os
import shutil
from pathlib import Path, PurePath
import pathlib
from stat import S_IREAD, S_IRGRP, S_IROTH
from hitsave.cloudstore import encode_hitsavemsg, request, create_header
import logging
from hitsave.session import Session

from hitsave.util import chunked_read, human_size

logger = logging.getLogger("hitsave")
BLOCK_SIZE = 2**20


@dataclass
class FileSnapshot:
    """This represents the state of a file on the host machine at a particular point in time.
    `@save`d methods can return these to make it clear that a function's result is stored in a file.
    You can then read this file directly
    """

    relpath: Optional[Path]
    """ original path on host machine, relative to the workspace directory.

    If it is None, then the file was snapshotted outside of the workspace directory."""

    name: str
    """ The name of the file. """

    digest: str
    """ BLAKE3 hash of the file """

    time: datetime
    """ Time at which the file was snap-shotted. """

    content_length: int
    """ Number of bytes of the file. """

    @property
    def local_cache_path(self) -> Path:
        """Returns the absolute path of the local cache file."""
        p = Config.current().local_cache_dir
        return p / "blobs" / self.digest

    @property
    def has_local_cache(self):
        """Returns true if the file has already been cached."""
        return self.local_cache_path.exists()

    @property
    def suffix(self):
        """The suffix extension of the file. Eg `hello.txt` has the suffix `.txt`."""
        return Path(self.name).suffix

    def download(self, force=False):
        """Download the file from the cloud to the local file cache."""
        if not force and self.has_local_cache:
            # no need to download
            return
        logger.info(f"Downloading {self.name} ({human_size(self.content_length)})")
        r = request("GET", f"/blob/{self.digest}")
        r.raise_for_status()
        # [todo] duplicated code.
        # [todo] exclusive file lock.
        with open(self.local_cache_path, "wb") as c:
            for chunk in r.iter_content(chunk_size=BLOCK_SIZE):
                c.write(chunk)
        # snapshot files are read only.
        # ref: https://stackoverflow.com/a/28492823/352201
        os.chmod(self.local_cache_path, S_IREAD | S_IRGRP)  # [todo] what about S_IROTH?
        return

    def open(self, mode="t", **kwargs) -> BufferedReader:
        """Open the snapshot in read mode. (writing to a snapshot is not allowed.)"""
        if not self.has_local_cache:
            self.download()
        fd: Any = open(self.local_cache_path, mode="r" + mode, **kwargs)
        return fd

    def restore_at(self, path: Path, overwrite=True) -> Path:
        """Restore the file at the given path. Returns the path of the restored file.
        If the given path is a directory, the file will be stored in the directory with the file's given basename.
        Otherwise the file will be saved at the exact path.
        If path has a different extension to the snapshot's path extension then we emit a value-error, because it's likely there was a mistake.
        """
        # [todo] directory exists
        # [todo] warn if overwriting
        # [todo] also we need to be aware of security auditing: https://peps.python.org/pep-0578/
        if not path.parent.exists():
            raise ValueError(f"Path {path.parent} does not exist.")
        if path.is_dir():
            logger.info(
                f"restore_at: {path} is a directory so appending the basename of the file {self.name}."
            )
            path = path / self.name
        if self.suffix != path.suffix:
            raise ValueError(
                f"Refusing to write to {path} since the extension name is different to extension of {self.relpath}"
            )
        if path.is_symlink():
            # [todo] if it links to our local cache then this is fine.
            # double check that the file exists
            logger.warn(f"restore over a symlink not implemented. {path}")
            pass
        if path.exists():
            if not overwrite:
                raise FileExistsError(f"Refusing to restore: would overwrite {path}.")
            else:
                # [todo] this can cause damage, we should make a new snapshot of this file so that we don't lose data.
                logger.info(
                    f"file {path} already exists, replacing with a symlink to {self.local_cache_path}"
                )
        path.symlink_to(self.local_cache_path)
        return path

    def restore(self, overwrite=True, project_path=None) -> Path:
        """Write the snapshot back to its original location (given by relpath).
        Returns the absolute path of the file that was restored."""
        if not self.has_local_cache:
            self.download()
        if self.relpath is None:
            raise ValueError(f"Can't restore a snapshot without a specific path.")
        project_path = Path(project_path or Config.current().workspace_dir)
        abspath = project_path / self.relpath
        assert abspath.is_relative_to(project_path)

        return self.restore_at(abspath, overwrite=overwrite)

    def restore_safe(self):
        if not self.has_local_cache:
            self.download()
        return self.local_cache_path

    @classmethod
    def snap(cls, path: Union[Path, str], workspace_dir=None):
        """Make a snapshot of the file at the given path.

        The path is stored relative to your workspace directory (either the location of your `pyproject.toml` or git root).
        """
        path = Path(path).resolve()
        # [todo] assert path is within project.
        # We should be very very careful about saving files from some arbitrary part of the disk.
        # [todo] assert that the file is finite (eg not `/dev/yes`)
        # [todo] do we need to lock files in case of multiprocessing? This is faff crossplatform
        if workspace_dir is None:
            workspace_dir = Config.current().workspace_dir
        if path.is_relative_to(workspace_dir):
            relpath = path.relative_to(workspace_dir)
        else:
            relpath = None
        time = datetime.now()
        with open(path, "rb") as fd:
            h = blake3()
            content_length = 0
            for data in chunked_read(fd):
                content_length += len(data)
                h.update(data)
            digest = h.hexdigest()
            fd.seek(0)
            snap = FileSnapshot(
                digest=digest,
                time=time,
                relpath=relpath,
                content_length=content_length,
                name=path.name,
            )
            if not snap.has_local_cache:
                # [todo] exclusive file lock.
                with open(snap.local_cache_path, "wb") as c:
                    while True:
                        # [todo] python must let you just pipe files?
                        data = fd.read(BLOCK_SIZE)
                        if not data:
                            break
                        c.write(data)
                # snapshot files are read only.
                # ref: https://stackoverflow.com/a/28492823/352201
                os.chmod(
                    snap.local_cache_path, S_IREAD | S_IRGRP
                )  # [todo] what about S_IROTH?
            # [todo] if not uploaded, initiate an upload here using /blobs
        return snap

    def upload(self):
        r = request("HEAD", f"/blob/{self.digest}")
        if r.status_code == 200:
            logger.info(f"File {self.name} is already uploaded.")
            return
        with self.open(mode="b") as f:
            msg = encode_hitsavemsg(
                {
                    "content_hash": self.digest,
                    "content_length": self.content_length,
                },
                f,
            )

            r = request("PUT", "/blob", data=msg)
            r.raise_for_status()
            logger.info(f"Uploaded {self.name} ({human_size(self.content_length)}).")


@dataclass
class DirectorySnapshot:
    """Similar to FileSnapshot, but snaps an entire directory.

    [todo]: archiving mode where it saves a directory as a .zip, .tar.gz or similar.
    """

    original_path: Path
    """ Path on users machine when the snapshot was taken. """

    relpath: Optional[Path]
    """ Path relative to the workspace directory of the code that snapshotted this directory.

    If it is none, then the snapshot was not taken on a directory that is in the workspace.
    """
    files: List[FileSnapshot]
    digest: str
    """ All files (including files in subdirectories),  """

    def download(self, force=False):
        for f in self.files:
            f.download(force=force)

    def restore_at(self, path: Path, overwrite=True) -> Path:
        """Restores the directory at the given path. Returns the path to the root of the snapshotted directory. (which is the same as the path argument)."""
        if path.exists():
            if overwrite:
                logger.info(
                    f"{path} already exists, files that are also present in the directory snapshot will be overwritten, other files will be left alone."
                )
        for file in self.files:
            assert (
                file.relpath is not None
            ), "malformed file snapshot in directory snapshot"
            filepath = path / file.relpath
            assert filepath.is_relative_to(
                path
            ), f"modification of files outside {path} is not allowed"

            filepath.parent.mkdir(parents=True, exist_ok=True)
            try:
                file.restore(overwrite=overwrite, project_path=path)
            except FileExistsError as e:
                logger.info(f"File {filepath} already exists, skipping.")
        return path

    def restore_safe(self) -> Path:
        """Restores the directory to a location in hitsave's cache directory (where we know that there is no chance of overwriting existing files)."""
        path: Path = (
            Config.current().local_cache_dir / "directory_snaps" / self.digest[:10]
        )
        if path.exists():
            logger.info(f"Directory snapshot already present {path}.")
            # [todo] check that the blobs have not been removed.
            return path
        path.mkdir(exist_ok=True, parents=True)
        return self.restore_at(path)

    def restore(self, workspace_dir=None, overwrite=True) -> Path:
        """Restores the snapshotted directory. Returns the path of the directory that was restored."""
        workspace_path = Path(workspace_dir or Config.current().workspace_dir)
        if self.relpath is None:
            raise ValueError(
                "Can't restore directory without specific path. Try using restore_safe."
            )
        abspath = workspace_path / self.relpath
        logger.info(f"Restoring directory snapshot at {abspath}.")
        self.restore_at(abspath, overwrite=overwrite)
        return abspath

    @classmethod
    def snap(cls, path, workspace_dir=None):
        path = Path(path).resolve()
        if workspace_dir is None:
            workspace_dir = Config.current().workspace_dir
        if path.is_relative_to(workspace_dir):
            relpath = path.relative_to(workspace_dir)
        else:
            logger.info(
                f"Directory {path} is outside workspace directory {workspace_dir}. Not storing a relpath."
            )
            relpath = None

        def rec(p: Path):
            for child_path in p.iterdir():
                if child_path.is_symlink():
                    # [todo] should be a warning
                    raise NotImplementedError(
                        "Directory snapshots containing symlinks is not supported yet."
                    )
                if child_path.is_dir():
                    yield from rec(child_path)
                if child_path.is_file():
                    yield FileSnapshot.snap(child_path, workspace_dir=path)

        files = sorted(rec(path), key=lambda x: x.relpath or 0)
        logger.info(f"Directory snapshot created for {len(files)} files.")
        h = blake3()
        for file in files:
            h.update(file.digest.encode())
        digest = h.hexdigest()
        snap = cls(relpath=relpath, files=files, digest=digest, original_path=path)
        return snap

    def upload(self):
        for file in self.files:
            file.upload()

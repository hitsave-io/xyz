from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from genericpath import isfile
from io import BufferedReader
from typing import Any, List, Union
from hitsave.config import Config
import os.path
from blake3 import blake3
import os
import shutil
from pathlib import Path, PurePath
import pathlib
from stat import S_IREAD, S_IRGRP, S_IROTH

import logging

logger = logging.getLogger("hitsave")


@dataclass
class FileSnapshot:
    """This represents the state of a file on the host machine at a particular point in time.
    `@save`d methods can return these to make it clear that a function's result is stored in a file.
    You can then read this file directly
    """

    relpath: PurePath
    """ original path on host machine, relative to the workspace directory."""

    digest: str
    """ BLAKE3 hash of the file """

    time: datetime
    """ Time at which the file was snap-shotted. """

    @property
    def local_cache_path(self) -> Path:
        """Returns the absolute path of the local cache file."""
        p = Config.current().local_cache_dir
        return p / "blobs" / self.digest

    @property
    def has_local_cache(self):
        """Returns true if the file has already been cached."""
        return self.local_cache_path.exists()

    def download(self, force=False):
        """Download the file from the cloud to the local file cache."""
        if not force and self.has_local_cache:
            # no need to download
            return
        raise NotImplementedError()

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
                f"restore_at: {path} is a directory so appending the basename of the file {self.relpath.name}."
            )
            path = path / self.relpath.name
        if self.relpath.suffix != path.suffix:
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
        project_path = Path(project_path or Config.current().workspace_dir)
        abspath = (project_path / self.relpath).resolve()
        assert abspath.is_relative_to(project_path)

        return self.restore_at(abspath, overwrite=overwrite)

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
        relpath = path.relative_to(workspace_dir)
        time = datetime.now()
        with open(path, "rb") as fd:
            block_size = 2**20
            h = blake3()
            while True:
                data = fd.read(block_size)
                if not data:
                    break
                h.update(data)
            digest = h.hexdigest()
            fd.seek(0)
            snap = FileSnapshot(digest=digest, time=time, relpath=relpath)
            if not snap.has_local_cache:
                # [todo] exclusive file lock.
                with open(snap.local_cache_path, "wb") as c:
                    while True:
                        # [todo] python must let you just pipe files?
                        # ?? os.sendfile() https://docs.python.org/3/library/os.html#os.sendfile
                        data = fd.read(block_size)
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


@dataclass
class DirectorySnapshot:
    """Similar to FileSnapshot, but snaps an entire directory.

    [todo]: archiving mode where it saves a directory as a .zip, .tar.gz or similar.
    """

    relpath: Path
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
        abspath = (workspace_path / self.relpath).resolve()
        logger.info(f"Restoring directory snapshot at {abspath}.")
        self.restore_at(abspath, overwrite=overwrite)
        return abspath

    @classmethod
    def snap(cls, path, workspace_dir=None):
        path = Path(path).resolve()
        if workspace_dir is None:
            workspace_dir = Config.current().workspace_dir
        if not path.is_relative_to(workspace_dir):
            # [todo]
            raise NotImplementedError(
                "Directory snapshots that are not in the project directory are not supported yet."
            )
        relpath = path.relative_to(workspace_dir)

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

        files = sorted(rec(path), key=lambda x: x.relpath)
        h = blake3()
        for file in files:
            h.update(file.digest.encode())
        digest = h.hexdigest()
        snap = cls(relpath=relpath, files=files, digest=digest)
        return snap

from dataclasses import dataclass
from datetime import datetime
from io import BufferedReader
from typing import Any
from hitsave.config import Config
import os.path
from blake3 import blake3
import os
import shutil


@dataclass
class FileSnapshot:
    """This represents the state of a file on the host machine at a particular point in time.
    `@save`d methods can return these to make it clear that a function's result is stored in a file.
    You can then read this file directly
    """

    relpath: str
    """ original path on host machine, relative to the workspace directory. """

    digest: str
    """ BLAKE3 hash of the file """

    time: datetime
    """ Time at which the file was snap-shotted. """

    @property
    def local_cache_path(self):
        """Returns the absolute path of the local cache file."""
        return os.path.join(Config.current().local_cache_dir, "blobs", self.digest)

    @property
    def has_local_cache(self):
        """Returns true if the file has already been cached."""
        return os.path.exists(self.local_cache_path)

    def download(self, force=False):
        """Download the file from the cloud to the local file cache."""
        if not force and self.has_local_cache:
            # no need to download
            return
        raise NotImplementedError()

    def open(self, mode="t", **kwargs) -> BufferedReader:
        if not self.has_local_cache:
            self.download()
        fd: Any = open(self.local_cache_path, mode="r" + mode, **kwargs)
        return fd

    def restore(self, overwrite=True, project_path=None):
        """Write the snapshot back to its original location (given by relpath)."""
        if not self.has_local_cache:
            self.download()
        if project_path is None:
            project_path = Config.current().workspace_dir
        abspath = os.path.normpath(os.path.join(os.curdir, self.relpath))
        # [todo] directory exists
        # [todo] warn if overwriting
        # [todo] another idea is to just symlink the file
        # [todo] also we need to be aware of security auditing: https://peps.python.org/pep-0578/
        shutil.copyfile(self.local_cache_path, abspath)
        return

    @classmethod
    def snap(cls, path, workspace_dir=None):
        """Make a snapshot of the file at the given path.

        The path is stored relative to your workspace directory (either the location of your `pyproject.toml` or git root).
        """
        # [todo] assert path is within project.
        # We should be very very careful about saving files from some arbitrary part of the disk.
        # [todo] assert that the file is finite (eg not `/dev/yes`)
        # [todo] do we need to lock files in case of multiprocessing? This is faff crossplatform
        if workspace_dir is None:
            workspace_dir = Config.current().workspace_dir
        relpath = os.path.relpath(path, start=workspace_dir)
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
                with open(snap.local_cache_path, "wb") as c:
                    while True:
                        # [todo] python must let you just pipe files?
                        # ?? os.sendfile() https://docs.python.org/3/library/os.html#os.sendfile
                        data = fd.read(block_size)
                        if not data:
                            break
                        c.write(data)
            # [todo] if not uploaded, initiate an upload here using /blobs
        return snap

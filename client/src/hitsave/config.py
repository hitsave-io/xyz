from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, fields, replace
import json
import re
import tempfile
import os
import os.path
import sys
import logging
from pathlib import Path
from typing import Literal, Optional, Type, TypeVar
import warnings
from hitsave.util import Current, as_optional, is_optional, get_git_root
import importlib.metadata

""" This module is responsible for loading all of the environment based config options.

[todo]: you want to get these args from
- environment variables
- cli arguments
- `.config/hitsave.toml` or similar

[todo] ensure that once the current config is set it can't be changed at runtime.

"""

logger = logging.getLogger("hitsave")

__version__ = importlib.metadata.version("hitsave")


def find_workspace_folder() -> Path:
    """This is our best guess to determine which folder is the developer's "workspace folder".
    This is the top level folder for the project that the developer is currently working on.

    Approaches tried:

    - for the cwd: look for a pyproject.toml
    - for the cwd: look for the git root of the cwd.

    """
    cwd = os.getcwd()
    # reference: https://github.com/python-poetry/poetry/pull/71/files#diff-e1f721c9a6040c5fbf1b5309d40a8f6e9604aa8b46469633edbc1e62da724e92
    def find(cwd, base):
        candidates = [Path(cwd), *Path(cwd).parents]
        for path in candidates:
            file = path / base
            if file.exists():
                logger.debug(f"Found a parent directory {path} with a {base}.")
                return path
        logger.debug(f"Couldn't find a {base} file for {cwd}.")
        return None

    p = find(cwd, "pyproject.toml")
    if p is not None:
        return p
    git_root = get_git_root()
    if git_root is not None:
        return Path(git_root)
    logger.warn(
        f"{cwd} is not in a git repository and no pyproject.toml could be found."
    )
    return Path(cwd)


appname = "hitsave"


def find_cache_directory() -> Path:
    """Returns the user-caching directory for the system. Trying to do it as canonically as possible.
    This is chosen to be the system-prescribed user-cache directory /hitsave.
    """
    if sys.platform == "darwin":
        # running macos https://apple.stackexchange.com/questions/316729/what-is-the-equivalent-of-cache-on-macos
        p = Path("~/Library/Caches")
    elif sys.platform == "linux":
        # https://wiki.archlinux.org/title/XDG_Base_Directory#User_directories
        p = Path(os.environ.get("XDG_CACHE_HOME", "~/.cache"))
    elif sys.platform == "win32":
        p = Path(os.environ.get("LOCALAPPDATA"))
    else:
        # [todo] windows
        logger.warning(
            f"Unknown platform {sys.platform}, user cache is defaulting to a tmpdir."
        )
        p = Path(tempfile.gettempdir())
    p = p.expanduser().resolve() / appname
    p.mkdir(exist_ok=True)
    (p / "blobs").mkdir(exist_ok=True)
    assert p.exists()
    return p


def find_global_config_directory() -> Path:
    """Returns a path to the place on the user's system where they want to store configs. Trying to do this as canonically as possible."""
    p = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
    if sys.platform == "darwin":
        # we are running macos, also use ~/.config.
        pass
    elif sys.platform == "linux":
        # https://wiki.archlinux.org/title/XDG_Base_Directory#User_directories
        pass
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA"))
    else:
        # [todo] windows.
        logger.warning(f"Unsupported platform {sys.platform}, using `~/.config`")
        pass
    p = p.expanduser().resolve() / appname
    p.mkdir(exist_ok=True)
    return p


def valid_api_key(k: str) -> bool:
    # https://stackoverflow.com/a/48730645/352201
    return re.match(r"^[\w-]+\Z", k) is not None


T = TypeVar("T")


def interpret_var_str(t: Type[T], value: str) -> T:
    """Given a string attained from an environment variable, make a best-effort attempt to parse it to an instance of the given type."""
    # [todo] this must be in argparse or something
    if t == str:
        return value  # type: ignore
    if t == int:
        return int(value)  # type: ignore
    if t == bool:
        return value not in ["False", "false", "0", "no"]  # type: ignore
    if t == Path:
        return Path(value)  # type: ignore
    X = as_optional(t)
    if X is not None:
        if value in ["None", "null", "undefined"]:
            return None  # type: ignore
        else:
            return interpret_var_str(X, value)

    raise NotImplementedError(f"Don't know how to interpret {t}")


@dataclass
class Config(Current):
    """This dataclass contains all of the configuration needed to use hitsave.

    [todo] some config that will be added later.
    - limits on local cache size

    [todo] features
    - merge with CLI arguments
    - merge with hitsave.toml files. `~/.config/hitsave.toml`, `$PROJECT/hitsave.toml` etc.

    """

    local_cache_dir: Path = field(default_factory=find_cache_directory)
    """ This is the directory where hitsave should store local caches of data. """

    cloud_url: str = field(default="http://api.hitsave.io")  # [todo] https
    """ URL for hitsave cloud API server. """

    workspace_dir: Path = field(default_factory=find_workspace_folder)
    """ Directory for the current project, should be the same as workspace_folder in vscode.
    It defaults to the nearest parent folder containing pyproject.toml or git root. """

    config_dir: Path = field(default_factory=find_global_config_directory)
    """ The root config directory. """

    no_advert: bool = field(default=False)
    """ If this is true then we won't bother you with a little advert for signing up to hitsave.io on exit. """

    no_local: bool = field(default=False)
    """ If this is true then don't use the local cache. """

    no_cloud: bool = field(default=False)
    """ If this is true then don't use the cloud cache. """

    version_sensitivity: Literal["none", "major", "minor", "patch"] = field(
        default="minor"
    )
    """ This is the sensitivity the digest algorithm should have to the versions of external packages.
    So if ``version_sensitivity = 'minor'``, then upgrading a package from ``3.2.0`` to ``3.2.1`` won't invalidate the cache,
    but upgrading to ``3.3.0`` will. Non-standard versioning schemes will always invalidate unless in 'none' mode.

    [todo] choose the sensitivity for different packages: do it by looking at the versioning sensitivity in requirements.txt or the lockfile.
           eventually remove this file.
    """

    @property
    def local_db_path(self) -> Path:
        """Gets the path to the local sqlite db that is used to store local state."""
        return self.local_cache_dir / "localstore.db"

    @property
    def api_key_file_path(self) -> Path:
        return self.config_dir / "api_keys.txt"

    @property
    def api_key(self):
        """The API key to authenticate cloud requests."""
        k = getattr(self, "_api_key", "MISSING")
        if k != "MISSING":
            return k
        p = self.api_key_file_path
        logger.debug(f"Looking for an API key for {self.cloud_url} at {p}.")
        if p.exists():
            with p.open("rt") as fd:
                keys = [l.rstrip().split("\t") for l in fd.readlines()]
                assert all(len(kv) == 2 for kv in keys), "malformed keys file"
                keys = {k: v for [k, v] in keys}
            key = keys.get(self.cloud_url, None)
            assert key is None or valid_api_key(key)
            self._api_key = key
        else:
            self._api_key = None
        if self._api_key == None:
            logger.debug("No API key found.")
        return self._api_key

    def set_api_key(self, k: str):
        # [todo] assert this looks like an api key.
        # [todo] file locking
        assert valid_api_key(k), "invalid api key"
        with self.api_key_file_path.open("at") as fd:
            fd.writelines(self.cloud_url + "\t" + k)
        self._api_key = k

    def merge_env(self):
        d = {}
        for fd in fields(self):
            k = fd.name
            v = os.environ.get(f"HITSAVE_{k.upper()}", None)
            if v is not None:
                d[k] = interpret_var_str(fd.type, v)
        return replace(self, **d)

    def __post_init__(self):
        if self.no_cloud and self.no_local:
            logger.warning(
                "Both of HITSAVE_NO_CLOUD and HITSAVE_NO_LOCAL were set. Defaulting to local-only."
            )
            self.no_local = True
            self.no_cloud = False
        if self.no_cloud:
            logger.warning(
                "NO_CLOUD is enabled. This means that you won't get all of the great features that hitsave has to offer!"
            )
        if self.no_local:
            # [todo] no_local is really only for development purposes I think we should remove it from the api.
            logger.warning(
                "NO_LOCAL is enabled. This means that results and blobs will not be cached locally which can use uneccessary bandwidth."
            )

    @classmethod
    def default(cls):
        """Creates the config, including environment variables and [todo] hitsave config files."""
        return cls().merge_env()


def no_local() -> bool:
    """Returns true when the no_local flag is set on the config."""
    return Config.current().no_local


def no_cloud() -> bool:
    """Returns true when the no_cloud flag is set on the config."""
    return Config.current().no_cloud

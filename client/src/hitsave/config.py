from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, fields, replace
import tempfile
import os
import os.path
import sys
import logging
from pathlib import Path
from typing import Optional, Type, TypeVar
from hitsave.util import as_optional, is_optional, get_git_root

""" This module is responsible for loading all of the environment based config options.

[todo]: you want to get these args from
- environment variables
- cli arguments
- `.config/hitsave.toml` or similar

"""

logger = logging.getLogger("hitsave")


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


def find_cache_directory():
    """Returns the user-caching directory for the system. Trying to do it as canonically as possible."""
    if sys.platform == "darwin":
        # running macos https://apple.stackexchange.com/questions/316729/what-is-the-equivalent-of-cache-on-macos
        p = "~/Library/Caches"
    elif sys.platform == "linux":
        # https://wiki.archlinux.org/title/XDG_Base_Directory#User_directories
        p = os.environ.get("XDG_CACHE_HOME", "~/.config")
    else:
        # [todo] windows
        logger.debug(f"Unknown platform {sys.platform}, defaulting to tmpdir.")
        p = tempfile.gettempdir()
    p = os.path.expanduser(p)
    p = os.path.join(p, "hitsave-io")
    return p


T = TypeVar("T")


def interpret_var_str(type: Type[T], value: str) -> T:
    # [todo] this must be in argparse or something
    if type == str:
        return value  # type: ignore
    if type == int:
        return int(value)  # type: ignore
    if type == bool:
        return value not in ["False", "false", "0", "no"]  # type: ignore
    if type == Path:
        return Path(value)  # type: ignore
    X = as_optional(type)
    if X is not None:
        if value in ["None", "null", "undefined"]:
            return None  # type: ignore
        else:
            return interpret_var_str(X, value)

    raise NotImplementedError(f"Don't know how to interpret {type}")


@dataclass
class Config:
    """This dataclass contains all of the configuration needed to use hitsave.

    [todo] some config that will be added later.
    - limits on local cache size

    [todo] features
    - merge with CLI arguments
    - merge with hitsave.toml files. `~/.config/hitsave.toml`, `$PROJECT/hitsave.toml` etc.
    """

    local_cache_dir: str
    """ This is the directory where hitsave should store local caches of data. """
    cloud_url: str
    """ URL for hitsave cloud API server.   """
    api_key: Optional[str]
    """ API key for hitsave cloud. """

    workspace_dir: str
    """ Directory for the current project, should be the same as workspace_folder in vscode. It defaults to the nearest
    parent folder containing pyproject.toml or git root. """

    no_advert: bool = field(default=False)
    """ If this is true then we won't bother you with a little advert for signing up to hitsave.io on exit. """

    no_local: bool = field(default=False)
    """ If this is true then don't use the local cache. """

    no_cloud: bool = field(default=False)
    """ If this is true then don't use the cloud cache. """

    def merge_env(self):
        d = {}
        for fd in fields(self):
            k = fd.name
            v = os.environ.get(f"HITSAVE_{k.upper()}", None)
            if v is not None:
                d[k] = interpret_var_str(fd.type, v)
        return replace(self, **d)

    @classmethod
    def init(cls):
        """Get the default config, without consulting files or environment varibles."""
        return cls(
            local_cache_dir=find_cache_directory(),
            cloud_url="https://api.hitsave.io",
            api_key=None,
            workspace_dir=str(find_workspace_folder()),
        )

    @classmethod
    def default(cls):
        """Creates the config, including environment variables and [todo] hitsave config files."""
        return cls.init().merge_env()

    @classmethod
    def current(cls):
        return current_config.get()


current_config: ContextVar[Config] = ContextVar(
    "current_config", default=Config.default()
)


@contextmanager
def use_config(conf: Config):
    t = current_config.set(conf)
    yield conf
    current_config.reset(t)

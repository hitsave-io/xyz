from dataclasses import asdict, dataclass, field, fields, replace
import re
import tempfile
import os
import os.path
import sys
from pathlib import Path
from typing import Literal, Optional, Type, TypeVar, Any, List, Dict, Iterable
from hitsave.util import Current, as_optional, is_optional, validate
from hitsave.util.config_file import interpret_var_str, get_config
import importlib.metadata
from hitsave.console import logger, user_info
from subprocess import PIPE, check_output, CalledProcessError
import io
import os
import subprocess
from hitsave.util import cache
from contextlib import redirect_stderr

__version__ = importlib.metadata.version("hitsave")


def get_git_root(cwd: Optional[Path] = None) -> Optional[Path]:
    """
    Gets the git root for the current working directory.

    source: https://github.com/maxnoe/python-gitpath/blob/86973f112b976a87e2ffa734fa2e43cc76dfe90d/gitpath/__init__.py
    (MIT licenced)
    """
    try:
        args = ["git", "rev-parse", "--show-toplevel"]
        logger.debug(f"Running {' '.join(args)} in {cwd or os.getcwd()}")
        r = subprocess.run(
            args,
            stdout=PIPE,
            stderr=PIPE,
            cwd=cwd,
            check=True,
        )
        if r.stdout == b"":
            return None
        return Path(r.stdout.decode().strip())
    except CalledProcessError as e:
        logger.debug("Not in a git repository:", e)
        return None


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
        p = Path(os.environ.get("LOCALAPPDATA", "~/.cache"))
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
    """Returns a path to the place on the user's system where they want to store configs.

    Trying to do this as canonically as possible."""
    p = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
    if sys.platform == "darwin":
        # we are running macos, also use ~/.config.
        pass
    elif sys.platform == "linux":
        # https://wiki.archlinux.org/title/XDG_Base_Directory#User_directories
        pass
    elif sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", "~/.config"))
    else:
        # [todo] windows.
        logger.warning(f"Unsupported platform {sys.platform}, using `~/.config`")
        pass
    p = p.expanduser().resolve() / appname
    p.mkdir(exist_ok=True)
    return p


def global_config_path():
    # [todo]  default config_dir defined in multiple places.
    return (
        Path(os.environ.get("HITSAVE_CONFIG_DIR", find_global_config_directory()))
        / "hitsave.conf"
    )


def valid_api_key(k: str) -> bool:
    """Checks whether the string is a valid API key."""
    # https://stackoverflow.com/a/48730645/352201
    return re.match(r"^[\w-]+\Z", k) is not None


CONSTS = {
    "default": {
        "web_url": "https://hitsave.io",
        "cloud_url": "https://api.hitsave.io",
        "github_client_id": "a569cafe591e507b13ca",
    },
}
""" Constants that are different in development environments. """
# [todo] the above should live in an .ini file or similar that varies in source control.


@cache
def get_default_constants():
    constants: dict = CONSTS["default"]
    # [todo] we can probably deduce whether we are a deployment build and disallow dev constants.
    env = os.environ.get("HITSAVE_ENV", None) or get_config(global_config_path(), "env")
    if env is not None:
        assert isinstance(env, str)
        if env not in CONSTS:
            logger.error(f"Unknown environment type '{env}' set.")
        else:
            logger.warning(
                f"Using the '{env}' development environment. Unset this with [green]hitsave config unset env[/green]"
            )
            constants.update(CONSTS[env])
    return constants


def get_default_constant(key):
    return lambda: get_default_constants()[key]


@dataclass
class Config(Current):
    """This dataclass contains all of the configuration needed to use hitsave."""

    cloud_url: str = field(default_factory=get_default_constant("cloud_url"))
    """ URL for hitsave cloud API server. """

    github_client_id: str = field(
        default_factory=get_default_constant("github_client_id")
    )
    """ This is the github client id used to authenticate the app. """

    web_url: str = field(default_factory=get_default_constant("web_url"))
    """ URL for the HitSave website. """

    local_cache_dir: Path = field(default_factory=find_cache_directory)
    """ This is the directory where hitsave should store local caches of data. """

    workspace_dir: Path = field(default_factory=find_workspace_folder)
    """ Directory for the current project, should be the same as workspace_folder in vscode.
    It defaults to the nearest parent folder containing pyproject.toml or git root. """

    config_dir: Path = field(default_factory=find_global_config_directory)
    """ The root config directory. """

    no_advert: bool = field(default=True)
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
    """

    @property
    def local_db_path(self) -> Path:
        """Gets the path to the local sqlite db that is used to store local state."""
        return self.local_cache_dir / "localstore.db"

    @property
    def api_key_file_path(self) -> Path:
        """Gets the path of the local file that contains the API keys of the application.
        Keys are stored as tab-separated (url, key) pairs.
        """
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
                keys = [kv for kv in keys if len(kv) == 2]
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
        """Save the given API key to the local API key store."""
        # [todo] file locking
        assert valid_api_key(k), "invalid api key"
        with self.api_key_file_path.open("at") as fd:
            fd.write(self.cloud_url + "\t" + k + "\n")
        self._api_key = k

    def merge_env(self):
        """Get config values from environment variables."""
        d = {}
        for fd in fields(self):
            k = fd.name
            K = f"HITSAVE_{k.upper()}"
            v = os.environ.get(K, None)
            if v is not None:
                logger.warn(f"Setting config {k} from environment variable {K}.")
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
            # [todo] no_local is really only for development purposes.
            logger.warning(
                "NO_LOCAL is enabled. This means that results and blobs will not be cached locally which can use unnecessary bandwidth."
            )

    @classmethod
    def default(cls):
        """Creates the config, including environment variables."""

        cfg = cls()

        from_global_file = get_config(
            global_config_path(), {field.name: field.type for field in fields(cls)}
        )

        cfg = replace(
            cfg,
            **from_global_file,
        )
        cfg = cfg.merge_env()
        return cfg

    @property
    def project_config_path(self):
        return self.workspace_dir / "hitsave.conf"


def no_local() -> bool:
    """Returns true when the no_local flag is set on the config."""
    return Config.current().no_local


def no_cloud() -> bool:
    """Returns true when the no_cloud flag is set on the config."""
    return Config.current().no_cloud

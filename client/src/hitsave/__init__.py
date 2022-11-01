import atexit
import sys

from .deephash import deephash
from .deepeq import deepeq
from .deep import reduce, reconstruct, traverse
from .decorator import memo
from .util import decorate_ansi, eprint, is_interactive_terminal
from .cli import app as main_cli
from .config import Config
from ._version import __version__
from .filesnap import FileSnapshot, DirectorySnapshot

__all__ = ["memo", "main_cli", "FileSnapshot", "DirectorySnapshot", "__version__"]

try:
    import hitsave.torch
except ModuleNotFoundError:
    pass


@atexit.register
def exit_message():
    """This is a (hopefully non-annoying) message that we show to the users to
    encourage them to sign up for some cloud storage.

    [todo] also if there is an error (eg 401), the message should be more sympathetic or omitted.
    [todo] don't show this if run from inside a package.
      eg suppose in the future numpy uses hitsave, then if a python user
      installs numpy but not explicitly hitsave, we should be silent.
    [todo] maybe also give some diagnostics; eg if max time on a saved function is <10ms then it's not worth caching.
    """
    cfg = Config.current()
    if cfg.api_key is not None:
        return
    if not is_interactive_terminal():
        return
    if cfg.no_advert:
        return
    time_saved = "10 minutes"  # [todo] accumulate
    if time_saved:
        eprint(f"You saved {time_saved} of compute time with hitsave.")
    eprint(
        "Get 5GB of free cloud cache:",
        "visit "
        + decorate_ansi("https://hitsave.io/signup", underline=True, fg="blue")
        + " or run "
        + decorate_ansi("hitsave keygen", fg="blue"),
        sep="\n",
    )

import atexit

from .decorator import memo, experiment
from .util import decorate_ansi, eprint, is_interactive_terminal
from .cli import app as main_cli
from .config import Config, __version__
from .filesnap import FileSnapshot, DirectorySnapshot

__all__ = [
    "memo",
    "main_cli",
    "FileSnapshot",
    "DirectorySnapshot",
    "__version__",
    "experiment",
]

try:
    import hitsave.torch
except ModuleNotFoundError:
    pass


@atexit.register
def exit_message():
    """This is a (hopefully non-annoying) message that we show to the users to
    encourage them to sign up for some cloud storage.
    """
    cfg = Config.current()
    if cfg.api_key is not None:
        return
    if not is_interactive_terminal():
        return
    if cfg.no_advert:
        return
    time_saved = "10 minutes"  # [todo]
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

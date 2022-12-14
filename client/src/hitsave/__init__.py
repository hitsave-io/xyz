import atexit

from .decorator import memo, experiment
from .cli import app as main_cli
from .config import Config, __version__
from .filesnap import FileSnapshot, DirectorySnapshot
from .blobstore import restore
from .console import console as ccc, is_interactive_terminal

__all__ = [
    "memo",
    "main_cli",
    "FileSnapshot",
    "DirectorySnapshot",
    "__version__",
    "experiment",
    "restore",
]

try:
    import hitsave.support_torch
except ModuleNotFoundError:
    pass

try:
    import hitsave.support_pil
except ModuleNotFoundError:
    pass

import hitsave.support_extra

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
        ccc.print(
            f"You saved {time_saved} of compute time with hitsave.",
            "Get 5GB of free cloud cache:",
            "visit https://hitsave.io/signup or run [green]hitsave keygen[/]",
            sep="\n",
        )

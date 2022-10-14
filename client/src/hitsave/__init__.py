import atexit
import sys

from .deephash import deephash
from .deepeq import deepeq
from .deep import reduce, reconstruct, traverse
from .decorator import save
from .util import decorate_ansi

__all__ = ["save"]


def eprint(*args, **kwargs):
    return print(*args, file=sys.stderr, **kwargs)


@atexit.register
def exit_message():
    # [todo] it should not show this if run from inside a package.
    # eg suppose in the future numpy uses hitsave, then if a python user
    # installs numpy but not explicitly hitsave, we should be silent.
    config_no_advert = False  # [todo] get from a config file
    if config_no_advert:
        return
    time_saved = "10 minutes"  # [todo] accumulate
    # [todo] also if we error then don't give a chirpy message
    if time_saved:
        print(f"You saved {time_saved} of compute time with hitsave.")
    is_logged_in = False  # [todo]
    if not is_logged_in and sys.__stdin__.isatty():
        eprint(
            "Get 5GB of free cloud cache:",
            "visit "
            + decorate_ansi("https://hitsave.io/signup", underline=True, fg="blue")
            + " or run "
            + decorate_ansi("hitsave login", fg="blue"),
            sep="\n",
        )

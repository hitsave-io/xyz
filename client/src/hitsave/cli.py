from pathlib import Path
from typing import Any, Dict, Optional
import typer
from dataclasses import fields, asdict
import asyncio
import platform
from enum import Enum
from hitsave.authenticate import (
    AuthenticationError,
    generate_api_key,
    get_jwt,
    loopback_login,
)
from hitsave.cloudutils import print_api_key_status, print_jwt_status
from hitsave.console import console, decorate, logger, user_info
from hitsave.config import Config, global_config_path
from hitsave.evalstore import EvalStore
from hitsave.blobstore import BlobStore
from hitsave.session import Session
from hitsave.filesnap import DirectorySnapshot, FileSnapshot
from hitsave.util.config_file import get_config, interpret_var_str, set_config
from rich.prompt import Confirm

from hitsave.console import is_interactive_terminal

app = typer.Typer()
""" Entrypoint for CLI tool. """


@app.command()
def login(
    no_autoopen: bool = typer.Option(
        False,
        "--no-autoopen",
    ),
):
    """Log in or sign up to the HitSave cloud service.

    This will present a link to you which can be used to register hitsave using your github account."""
    autoopen = not no_autoopen
    asyncio.run(loopback_login(autoopen=autoopen))


async def keygen_async():
    """Interactive workflow for generating a new api key."""
    cfg = Config.current()
    if cfg.api_key is not None:
        console.print(f"An API key for hitsave is already present.")
        if is_interactive_terminal():
            r = Confirm.ask("Do you wish to generate another API key?")
            if not r:
                return
    label = platform.node()

    async def login():
        if is_interactive_terminal():
            await loopback_login()
        else:
            raise AuthenticationError(
                "Please login by running `hitsave login` in an interactive terminal."
            )

    if get_jwt() is None:
        await login()
    try:
        api_key = await generate_api_key(label)
    except AuthenticationError as err:
        console.print("Authentication session expired, please log in again:")
        await login()
        api_key = await generate_api_key(label)

    if not is_interactive_terminal():
        # if a human is not viewing the terminal, it should just print
        # api_key on stdout and exit.
        print(api_key)
        return
    console.print(
        "API keys are used to provide programmatic access to the HitSave cloud API.\n",
        "This API key should be stored in a secret location and not shared, as anybody\ncan use it to authenticate as you.",
        "To revoke an API key, visit https://hitsave.io/my-keys",
        # "Otherwise, [see here]() for other ways to load your API key into the HitSave client.",
        "\n\n",
        f"[green bold]{api_key}[/]" "\n",
        sep="",
    )
    console.print(f"Saving key to {cfg.api_key_file_path}.")
    cfg.set_api_key(api_key)
    doc_url = "https://docs.hitsave.io/keys"
    console.print(
        f"Please see {doc_url} for ways you can include this key in your environment."
    )


@app.command()
def keygen(label: Optional[str] = None):
    """Generate a fresh API key.

    If the current shell is zsh, you will also be asked whether you
    want to append the API key to your .zshenv file.
    """
    asyncio.run(keygen_async())


@app.command()
def snapshot(path: Path = typer.Argument(..., exists=True)):
    """Upload the given file or directory to the cloud, returning a digest that can be used to reference data in code."""
    if path.is_file():
        snap = FileSnapshot.snap(path)
        snap.upload()
        print(snap.digest)
    elif path.is_dir():
        snap = DirectorySnapshot.snap(path)
        snap.upload()
        print(snap.digest)
    else:
        raise ValueError(f"Can't snapshot {path}.")


class Scope(Enum):
    Global = "global"
    Project = "project"


config_subcommand = typer.Typer()
app.add_typer(
    config_subcommand, name="config", short_help="Manage HitSave config files."
)

config_state = {"scope": "global"}


def get_config_path():
    return (
        global_config_path()
        if config_state["scope"] == "global"
        else Config.current().project_config_path
    )


@config_subcommand.command()
def set(
    key: str,
    value: str,
):
    """Add a key/value pair to the HitSave config."""
    field = Config.__dataclass_fields__.get(key, None)
    type = field.type if field else str
    item = interpret_var_str(type, value)
    p = get_config_path()
    set_config(p, **{key: item})
    user_info(
        "Setting",
        decorate(key, "yellow"),
        ":",
        decorate(type.__name__, "cyan"),
        "←",
        repr(item),
        "in",
        p,
    )


@config_subcommand.command()
def unset(
    key: str,
):
    """Unset an option in the HitSave config."""
    p = get_config_path()
    set_config(p, **{key: None})
    user_info("Unsetting", decorate(key, "yellow"), "in", p)


@config_subcommand.command()
def get(
    key: str,
):
    """Read an option from the HitSave config."""
    v = get_config(get_config_path(), key)
    if v is None:
        print(f"option {key} is not set")
    else:
        print(v)


@config_subcommand.command()
def list():
    """List the values in the current hitsave config."""
    cfg = Config.current()
    for k in cfg.__dataclass_fields__.keys():
        print(f"{k} = {getattr(cfg, k)}")


@config_subcommand.callback()
def config_main(
    is_global: bool = typer.Option(False, "--global"),
    is_project: bool = typer.Option(False, "--project"),
):
    if is_global and is_project:
        raise ValueError("Only one of --global and --project allowed.")
    if is_global:
        config_state["scope"] = "global"
    elif is_project:
        config_state["scope"] = "project"


@app.command()
def clear_local():
    """Obliterates all local cache and blobs."""
    es = EvalStore.current()
    bs = BlobStore.current()
    user_info(
        "[red]Deleting everything from your local cache.[/]",
        f"\nevals: {len(es.local)}, blobs: {len(bs.local)}",
        # "\nAny file snapshot symlinks will need to be restored.",
    )
    c = Confirm.ask("Delete local cache?")
    if c:
        user_info(f"Dropping {len(es.local)} evals.")
        es.clear_local()
        bs = BlobStore.current()
        bs.clear_local()
        bs.prune_local()
    else:
        user_info("Clear aborted.")


@app.command()
def status():
    """Prints details of hitsave's connection"""
    jc = print_jwt_status()
    print_api_key_status()
    # [todo] info about local cache for the given project.

if __name__ == "__main__":
    app()

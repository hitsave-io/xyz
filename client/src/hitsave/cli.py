from pathlib import Path
from typing import Dict, Optional
import typer
from dataclasses import fields, asdict
import asyncio
import platform
from enum import Enum
import logging
from hitsave.authenticate import (
    AuthenticationError,
    generate_api_key,
    get_jwt,
    loopback_login,
)
from hitsave.config import Config
from hitsave.evalstore import EvalStore
from hitsave.blobstore import BlobStore
from hitsave.session import Session
from hitsave.filesnap import DirectorySnapshot, FileSnapshot
from hitsave.util import decorate_ansi, decorate_url, eprint, is_interactive_terminal

app = typer.Typer()
""" Entrypoint for CLI tool. """

logger = logging.getLogger("hitsave")
# logger.setLevel(logging.DEBUG)


@app.command()
def serve():
    """Runs the hitsave LSP server."""
    from hitsave.server import main

    main()


@app.command()
def login():
    """Log in or sign up to the HitSave cloud service.

    This will present a link to you which can be used to register hitsave using your github account."""
    asyncio.run(loopback_login())


async def keygen_async():
    """Interactive workflow for generating a new api key."""
    cfg = Config.current()
    if cfg.api_key is not None:
        eprint("Warning: an API key for hitsave is already present.")
        if is_interactive_terminal():
            eprint(
                "Please press enter to confirm that you wish to generate another API key."
            )
            input(">")
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
        eprint("Authentication session expired, please log in again:")
        await login()
        api_key = await generate_api_key(label)

    if not is_interactive_terminal():
        # if a human is not viewing the terminal, it should just print
        # api_key on stdout and exit.
        print(api_key)
        return
    eprint(
        "API keys are used to provide programmatic access to the HitSave cloud API.\n",
        "This API key should be stored in a secret location and not shared, as anybody\ncan use it to authenticate as you.",
        "To revoke an API key, visit ",
        decorate_url("https://hitsave.io/my-keys"),
        # "Otherwise, [see here]() for other ways to load your API key into the HitSave client.",
        "\n\n",
        decorate_ansi(api_key, bold=True, fg="green"),
        "\n",
        sep="",
    )
    eprint(f"Saving key to {cfg.api_key_file_path}.")
    cfg.set_api_key(api_key)
    doc_url = decorate_url("https://hitsave.io/doc/keys")
    eprint(
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
def clear_local():
    """Deletes the local eval store (not cached blobs)."""
    store = EvalStore().local
    p = Config.current().local_db_path
    eprint(f"Deleting {len(store)} entries in {p}")
    store.clear()


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
        Config.global_config_path()
        if config_state["scope"] == "global"
        else Config.current().project_config_path
    )


@config_subcommand.command()
def set(
    key: str,
    value: str,
    is_global: bool = typer.Option(False, "--global"),
    is_project: bool = typer.Option(False, "--project"),
):
    """Add a key/value pair to the HitSave config."""
    Config.set_config_file(get_config_path(), **{key: value})


@config_subcommand.command()
def unset(
    key: str,
    is_global: bool = typer.Option(False, "--global"),
    is_project: bool = typer.Option(False, "--project"),
):
    """Unset an option in the HitSave config."""
    Config.set_config_file(get_config_path(), **{key: None})


@config_subcommand.command()
def get(
    key: str,
):
    """Read an option from the HitSave config."""
    v = Config.read_key_from_config_file(get_config_path(), key)
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


if __name__ == "__main__":
    app()

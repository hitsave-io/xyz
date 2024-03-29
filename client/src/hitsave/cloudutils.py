from io import BufferedReader
import io
from pathlib import Path
from typing import IO, Any, Dict, Iterable, Iterator, Literal, Optional
import logging
import json
from hitsave.config import Config
from hitsave.util import chunked_read, human_size
import requests
from urllib3.exceptions import NewConnectionError
from rich import print

logger = logging.getLogger("hitsave")

"""
The HitSave wire format is a utf-8 encoded JSON object followed by raw bytes stream.

- 4 byte unsigned integer; the content length of the JSON part,
- n bytes; the utf-8 encoded JSON object.
- bytestream

 """


def create_header(meta: dict) -> bytes:
    """Creates a header for the HitSave wire format."""
    meta_json = json.dumps(meta).encode("utf-8")
    json_len = len(meta_json).to_bytes(4, byteorder="big", signed=False)
    return json_len + meta_json


def encode_hitsavemsg(meta: dict, payload: IO[bytes]) -> Iterator[bytes]:
    yield create_header(meta)
    yield from chunked_read(payload)


def read_header(file: BufferedReader) -> dict:
    l = int.from_bytes(file.read(4), byteorder="big", signed=False)
    j = json.loads(file.read(l).decode("utf-8"))
    return j


class ConnectionError(Exception):
    """Represents a failure to connect to the cloud server."""

    pass


class AuthenticationError(ConnectionError):
    """Raised when the user is not authenticated.

    That is, the JWT or API key is nonexistent or not valid."""


def jwt_path() -> Path:
    return Config.current().local_cache_dir / "hitsave-session.jwt"


def save_jwt(jwt: str):
    p = jwt_path()
    if p.exists():
        logger.debug(f"File {p} already exists, overwriting.")
    else:
        logger.debug(f"Writing authentication JWT to {p}.")
    with open(p, "wt") as file:
        file.write(jwt)


def get_jwt() -> Optional[str]:
    """Gets the cached JWT. If it doesn't exist, returns none."""
    p = jwt_path()
    if not p.exists():
        logger.debug(f"File {p} does not exist.")
        return None
    with open(p, "rt") as file:
        logger.debug(f"Reading JWT from {p}.")
        return file.read()


def erase_jwt():
    p = jwt_path()
    p.unlink()


already_reported_connection_error = False
""" This is true to only report a bad connection as a warning once. """


def print_jwt_status() -> bool:
    """Returns true if we are authenticated with a JWT auth."""
    jwt = get_jwt()
    if jwt is None:
        print("Not logged in.")
        return False
    headers = {"Authorization": f"Bearer {jwt}"}
    response = request("GET", "/user", headers=headers)
    if response.status_code == 200:
        print("Logged in.")
        return True
    if response.status_code == 401:
        erase_jwt()
        print("Login session expired.")
        return False
    if response.status_code == 403:
        erase_jwt()
        print("Invalid JWT. Deleting.")
        return False
    response.raise_for_status()
    raise NotImplementedError(response)


def print_api_key_status() -> None:
    api_key = Config.current().api_key
    if api_key is None:
        print("No API key found.")
        return
    response = request("GET", "/user")
    if response.status_code == 200:
        print("API key valid.")
    elif response.status_code == 401:
        print("API key not valid.")
    else:
        response.raise_for_status()
        print("Unknown response", response.status_code, response.text)


def request(
    method: str, path, headers: Dict[str, str] = {}, **kwargs
) -> requests.Response:
    """Sends an HTTP request to the hitsave api, we provide the right authentication headers.

    Uses the same signature as ``requests.request``.
    You can perform a streaming upload by passing an Iterable[bytes] as the ``data`` argument.

    Reference: https://requests.readthedocs.io/en/latest/user/advanced/#streaming-uploads

    Raises a ConnectionError if we can't connect to the cloud.
    """
    global already_reported_connection_error
    if "Authorization" not in headers:
        api_key = Config.current().api_key
        if api_key is None:
            raise AuthenticationError(
                "No API key found. Please create an API key with `hitsave keygen`"
            )
        headers = {"Authorization": api_key, **headers}
    cloud_url = Config.current().cloud_url
    try:
        r = requests.request(method, cloud_url + path, **kwargs, headers=headers)
        return r
    except (requests.exceptions.ConnectionError, NewConnectionError) as err:
        if not already_reported_connection_error:
            logger.warning(
                f"Could not reach {cloud_url}. Using HitSave in offline mode."
            )
            already_reported_connection_error = True
        raise ConnectionError from err

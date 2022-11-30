from io import BufferedReader
import io
from typing import IO, Any, Iterable, Iterator, Literal
import logging
import json
from hitsave.config import Config
from hitsave.util import chunked_read, human_size
import requests
from urllib3.exceptions import NewConnectionError

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


class AuthenticationError(Exception):
    """Raised when the user is not authenticated.

    That is, the JWT or API key is nonexistent or not valid."""


already_reported_connection_error = False
""" This is true to only report a bad connection as a warning once. """


def request(method: str, path, **kwargs) -> requests.Response:
    """Sends an HTTP request to the hitsave api, we provide the right authentication headers.

    Uses the same signature as ``requests.request``.
    You can perform a streaming upload by passing an Iterable[bytes] as the ``data`` argument.

    Reference: https://requests.readthedocs.io/en/latest/user/advanced/#streaming-uploads

    Raises a ConnectionError if we can't connect to the cloud.
    """
    global already_reported_connection_error
    api_key = Config.current().api_key
    if api_key is None:
        raise AuthenticationError(
            "No API key found. Please create an API key with `hitsave keygen`"
        )
    headers: Any = {
        "Authorization": Config.current().api_key,
    }
    headers.update(kwargs.get("headers", {}))
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

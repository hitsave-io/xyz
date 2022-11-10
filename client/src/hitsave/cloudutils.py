from io import BufferedReader
import io
from typing import IO, Any, Iterable, Iterator, Literal
import logging
import json
from hitsave.config import Config
from hitsave.util import chunked_read, human_size
import requests
from urllib3.exceptions import NewConnectionError

from hitsave.visualize import visualize_rec

logger = logging.getLogger("hitsave")

# streaming uploads https://requests.readthedocs.io/en/latest/user/advanced/#streaming-uploads
def create_header(meta: dict) -> bytes:
    """Creates a header for the hitsave wire format"""
    with io.BytesIO() as tape:
        meta_json = json.dumps(meta).encode("utf-8")
        json_len = len(meta_json).to_bytes(4, byteorder="big", signed=False)
        tape.write(json_len)
        tape.write(meta_json)
        tape.seek(0)
        return tape.read()


def encode_hitsavemsg(meta: dict, payload: IO[bytes]) -> Iterator[bytes]:
    yield create_header(meta)
    yield from chunked_read(payload)


def read_header(file: BufferedReader) -> dict:
    l = int.from_bytes(file.read(4), byteorder="big", signed=False)
    j = json.loads(file.read(l).decode("utf-8"))
    return j


class ConnectionError(Exception):
    """Represents a failure to connect to the hitsave server."""

    pass


already_reported_connection_error = False


def request(method: str, path, **kwargs) -> requests.Response:
    """Runs a requests.request to the hitsave api, we provide the right authentication headers.

    [todo] eventually this will also reuse existing connections if it can.
    """
    global already_reported_connection_error
    api_key = Config.current().api_key
    if api_key is None:
        # [todo] should use AuthorizationError.
        # [todo] use jwt if you can.
        raise Exception(
            "No API key found. Please create an API key with hitsave keygen"
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

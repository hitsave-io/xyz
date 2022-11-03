from io import BufferedReader
import io
from typing import IO, Any, Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import Optional, Union
from hitsave.codegraph import Symbol
from hitsave.types import EvalKey, Eval, StoreMiss
import logging
import json
from blake3 import blake3
from hitsave.config import Config
from datetime import datetime
from hitsave.util import chunked_read
import pickle
import requests
from itertools import chain
import tempfile
import dateutil.parser

from hitsave.visualize import visualize_rec

logger = logging.getLogger("hitsave")

# streaming uploads https://requests.readthedocs.io/en/latest/user/advanced/#streaming-uploads
def create_header(meta: dict) -> bytes:
    """Creates a header for the hitsave format"""
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


def request(method: str, path, **kwargs):
    """Runs a requests.request to the hitsave api, we provide the right authentication headers.

    [todo] this will also reuse existing connections if it can.
    """
    api_key = Config.current().api_key
    if api_key is None:
        # [todo] should use AuthorizationError.
        raise Exception(
            "No API key found. Please create an API key with hitsave keygen"
        )
    headers: Any = {
        "Authorization": Config.current().api_key,
    }
    headers.update(kwargs.get("headers", {}))
    cloud_url = Config.current().cloud_url
    r = requests.request(method, cloud_url + path, **kwargs, headers=headers)
    return r


@dataclass
class CloudStore:
    """Store connected to the hitsave cloud api.

    [todo] abstract over transport, rpc etc
    [todo] consider using [marshmallow](https://marshmallow.readthedocs.io/en/stable/) instead of pickle.
    """

    api_key: Optional[str] = field(default_factory=lambda: Config.current().api_key)

    def close(self):
        pass

    def request_eval(self, key: EvalKey, method: str = "GET") -> requests.Response:
        q = dict(
            fn_key=str(key.fn_key),
            fn_hash=key.fn_hash,
            args_hash=key.args_hash,
            # if poll is true, we increment a counter in the HitSave database. We use this to show you metrics about time saved etc.
            poll="true",
        )
        assert self.api_key is not None
        r = request("GET", "/eval", params=q)
        return r

    def poll(self, key: EvalKey) -> None:
        self.request_eval(key)

    def get(self, key: EvalKey) -> Union[Eval, StoreMiss]:
        try:
            r = self.request_eval(key)
            if r.status_code == 404:
                return StoreMiss("Not found.")
            if r.status_code == 403:
                # [todo] unauthorized
                pass
            r.raise_for_status()
        except Exception as err:
            msg = f"Request failed: {err}"
            logger.error(msg)
            return StoreMiss(msg)
        results: list = r.json()
        if len(results) > 1:
            # [todo] change api to only ever return at most one result.
            logger.warn(f"got multiple results for the same query??")
        for result in results:
            logger.info(f"downloaded result for {repr(key)}")
            content_hash = result["content_hash"]
            r = request("GET", f"/blob/{content_hash}")
            r.raise_for_status()
            # [todo] should really stream this. https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
            bs = r.content
            # [todo] we need to use a custom pickler that throws when the instance being created changes.
            # for example, if we are making a dataclass, we need to validate that all of the fields are present.
            content = pickle.loads(bs)
            e = Eval(
                key=EvalKey(
                    fn_key=CodeVertex.of_str(result["fn_key"]),
                    fn_hash=result["fn_hash"],
                    args_hash=result["args_hash"],
                ),
                args=result["args"],
                result=content,
                is_experiment=result.get("is_experiment", False),
                start_time=dateutil.parser.isoparse(result["start_time"]),
                elapsed_process_time=result["elapsed_process_time"],
            )
            return e
        return StoreMiss("No results.")

    def set(self, e: Eval):

        content_length = 0
        h = blake3()
        with tempfile.SpooledTemporaryFile() as tape:
            pickle.dump(e.result, tape)
            tape.seek(0)
            for x in chunked_read(tape):
                content_length += len(x)
                h.update(x)
            digest = h.hexdigest()
            tape.seek(0)
            args = e.args
            if args is not None:
                assert isinstance(args, dict)
                args = {k: visualize_rec(v) for k, v in args.items()}
                # [todo] if an arg is too big, we blobify it and replace with {__kind__: blob, ...}

            result = encode_hitsavemsg(
                dict(
                    fn_key=str(e.key.fn_key),
                    fn_hash=e.key.fn_hash,
                    args_hash=e.key.args_hash,
                    args=args,
                    content_hash=digest,
                    content_length=content_length,
                    is_experiment=e.is_experiment,
                    start_time=e.start_time.isoformat(),
                    elapsed_process_time=e.elapsed_process_time,
                    result_json=visualize_rec(e.result),
                ),
                tape,
            )
            try:
                r = request("PUT", f"/eval/", data=result)
                r.raise_for_status()
            except Exception as err:
                # [todo] manage errors
                # they should all result in the user being given some friendly advice about
                # how they can make sure their thing is uploaded.
                logger.error(err)


if __name__ == "__main__":
    cs = CloudStore()

    e = Eval(
        EvalKey(
            fn_key=CodeVertex.of_str("test:test"),
            fn_hash="deadbeef",
            args_hash="cabbage",
        ),
        result="hello world",
        start_time=datetime.now(),
        elapsed_process_time=1000,
        is_experiment=False,
    )

    cs.set(e)

    ee = cs.get(e.key)

    assert isinstance(ee, Eval)
    assert ee.result == e.result

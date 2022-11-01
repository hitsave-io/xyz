from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional, Union
from hitsave.codegraph import CodeVertex
from hitsave.types import EvalKey, Eval, StoreMiss
import msgpack
import requests
import logging
import json
from blake3 import blake3
from hitsave.config import Config
import pickle
import dateutil.parser

logger = logging.getLogger("hitsave")


def dumps(meta: dict, blob: bytes):
    """Hitsave eval upload blob upload encoding:"""
    meta_json = json.dumps(meta).encode("utf-8")
    json_len = len(meta_json).to_bytes(4, byteorder="big")
    return json_len + meta_json + blob


@dataclass
class CloudStore:
    """Store connected to the hitsave cloud api.

    [todo] abstract over transport, rpc etc
    [todo] consider using [marshmallow](https://marshmallow.readthedocs.io/en/stable/) instead of pickle.
    """

    url: str = field(default_factory=lambda: Config.current().cloud_url)
    api_key: Optional[str] = field(default_factory=lambda: Config.current().api_key)

    def close(self):
        pass

    def request(self, key: EvalKey, method: str = "GET") -> requests.Response:
        q = dict(
            fn_key=str(key.fn_key),
            fn_hash=key.fn_hash,
            args_hash=key.args_hash,
            # if poll is true, we increment a counter in the HitSave database. We use this to show you metrics about time saved etc.
            poll="true",
        )
        assert self.api_key is not None
        headers = {
            "Authorization": self.api_key,
        }
        r = requests.request(
            method,
            f"{self.url}/eval",
            params=q,
            headers=headers,
        )
        return r

    def poll(self, key: EvalKey) -> None:
        self.request(key)

    def get(self, key: EvalKey) -> Union[Eval, StoreMiss]:
        try:
            r = self.request(key)
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
            r = requests.request(
                "GET",
                f"{self.url}/blob/{content_hash}",
                headers={
                    "Authorization": self.api_key,
                },
            )
            r.raise_for_status()
            bs = r.content
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
        pickled = pickle.dumps(e.result)
        content_hash = blake3(pickled).hexdigest()
        content_length = len(pickled)

        m = dumps(
            dict(
                fn_key=str(e.key.fn_key),
                fn_hash=e.key.fn_hash,
                args_hash=e.key.args_hash,
                args=e.args,
                content_hash=content_hash,
                content_length=content_length,
                is_experiment=e.is_experiment,
                start_time=e.start_time.isoformat(),
                elapsed_process_time=e.elapsed_process_time,
            ),
            pickled,
        )

        try:
            assert self.api_key is not None
            headers = {
                "Content-type": "application/x-msgpack",  # https://github.com/msgpack/msgpack/issues/194
                "Authorization": self.api_key,
            }
            r = requests.put(f"{self.url}/eval/", m, headers=headers)
            r.raise_for_status()
        except Exception as err:
            # [todo] manage errors
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
    )

    cs.set(e)

    ee = cs.get(e.key)

    assert isinstance(ee, Eval)
    assert ee.result == e.result

from dataclasses import asdict, dataclass, field
from typing import Optional, Union
from hitsave.codegraph import CodeVertex
from hitsave.types import EvalKey, Eval, StoreMiss
import msgpack
import requests
import logging
import json
from hitsave.config import cloud_url, cloud_api_key
import pickle

logger = logging.getLogger("hitsave")


@dataclass
class CloudStore:
    """Store connected to the hitsave cloud api.

    [todo] abstract over transport, rpc etc
    """

    url: str = field(default=cloud_url)
    api_key: Optional[str] = field(default=cloud_api_key)

    def close(self):
        pass

    def get(self, key: EvalKey) -> Union[Eval, StoreMiss]:
        ks = str(key)
        q = dict(
            fn_key=str(key.fn_key),
            fn_hash=key.fn_hash,
            args_hash=key.args_hash,
        )
        j = json.dumps(q)
        try:
            assert self.api_key is not None
            headers = {
                "Content-type": "application/json",
                "Authorization": self.api_key,
            }
            r = requests.request(
                "GET",
                f"{self.url}/eval/",
                data=j,
                headers=headers,
            )
            if r.status_code == 404:
                return StoreMiss("Not found.")
            r.raise_for_status()
        except Exception as err:
            msg = f"Request failed: {err}"
            logger.error(msg)
            return StoreMiss(msg)
        d: dict = msgpack.loads(r.content)  # type: ignore
        results = d.get("results", [])
        if len(results) > 1:
            # [todo] change api to only ever return at most one result.
            logger.warn(f"got multiple results for the same query??")
        for result in results:
            logger.info(f"downloaded result for {repr(key)}")
            e = Eval(
                key=EvalKey(
                    fn_key=CodeVertex.of_str(result["fn_key"]),
                    fn_hash=result["fn_hash"],
                    args_hash=result["args_hash"],
                ),
                args=result["args"],
                result=pickle.loads(result["result"]),
            )
            return e
        return StoreMiss("No results.")

    def set(self, e: Eval):
        m: bytes = msgpack.dumps(
            dict(
                fn_key=str(e.key.fn_key),
                fn_hash=e.key.fn_hash,
                args_hash=e.key.args_hash,
                args=e.args,
                result=pickle.dumps(e.result),
                # [todo] this is silly.
            )
        )  # type: ignore

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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional
from hitsave.server.lsptypes import ClientInfo
import os


@dataclass
class InitParams:
    type: Literal["user-process", "kernel", "webview", "proxy-session"]
    clientInfo: ClientInfo = field(default_factory = ClientInfo)
    workspace_dir: Optional[str] = field(default=None)
    processId: Optional[int] = field(default=os.getpid())

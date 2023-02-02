from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional
from hitsave.__about__ import __version__
import urllib.parse

DocumentUri = str

# [todo] use TypedDict instead?


def path_of_uri(uri: DocumentUri):
    x = urllib.parse.urlparse(uri)
    assert x.netloc == ""
    assert x.scheme == "file"
    return Path(x.path)


@dataclass
class TextDocumentIdentifier:
    uri: str
    version: Optional[int]

    def __fspath__(self):
        return str(path_of_uri(self.uri))


@dataclass
class Position:
    line: int
    character: int


@dataclass
class Range:
    start: Position
    end: Position

    @classmethod
    def mk(cls, l0: int, c0: int, l1: int, c1: int):
        return cls(Position(l0, c0), Position(l1, c1))


@dataclass
class TextDocumentContentChangeEvent:
    range: Optional[Range]
    rangeLength: Optional[int]
    text: str


@dataclass
class TextDocumentParams:
    textDocument: TextDocumentIdentifier

    def __fspath__(self):
        return self.textDocument.__fspath__()


@dataclass
class TextDocumentPositionParams:
    textDocument: TextDocumentIdentifier
    position: Position


@dataclass
class DidChangeTextDocumentParams:
    """
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#didChangeTextDocumentParams
    """

    textDocument: TextDocumentIdentifier
    contentChanges: list[TextDocumentContentChangeEvent]


@dataclass
class ClientInfo:
    name: str = field(default="hitsave")
    version: Optional[str] = field(default=__version__)


@dataclass
class WorkspaceFolder:
    uri: DocumentUri
    name: str


@dataclass
class TextDocumentSyncClientCapabilities:
    dynamicRegistration: Optional[bool]
    willSave: Optional[bool]
    willSaveWaitUntil: Optional[bool]
    didSave: Optional[bool]


@dataclass
class CodeLensClientCapabilities:
    dynamicRegistration: Optional[bool]


@dataclass
class TextDocumentClientCapabilities:
    synchronization: Optional[TextDocumentSyncClientCapabilities]
    codeLens: Optional[CodeLensClientCapabilities]


@dataclass
class ClientCapabilities:
    textDocument: Optional[TextDocumentClientCapabilities]


@dataclass
class InitializeParams:
    processId: Optional[int] = field(default=None)
    locale: Optional[str] = field(default=None)
    workspaceFolders: Optional[list[WorkspaceFolder]] = field(default=None)
    clientInfo: Optional[ClientInfo] = field(default_factory=ClientInfo)
    initializationOptions: Optional[Any] = field(default=None)
    capabilities: Optional[ClientCapabilities] = field(default=None)
    trace: Optional[Literal["off", "messages", "verbose"]] = field(default=None)


class PositionEncodingKind(Enum):
    UTF8 = "utf-8"
    UTF16 = "utf-16"
    UTF32 = "utf-32"


class TextDocumentSyncKind(Enum):
    none = 0
    full = 1
    incremental = 2


@dataclass
class TextDocumentSyncOptions:
    openClose: Optional[bool] = field(default=None)
    change: Optional[TextDocumentSyncKind] = field(default=None)


@dataclass
class CodeLensOptions:
    resolveProvider: Optional[bool] = field(default=None)


@dataclass
class ServerCapabilities:
    positionEncoding: Optional[PositionEncodingKind] = field(default=None)
    textDocumentSync: Optional[TextDocumentSyncOptions] = field(default=None)
    codeLensProvider: Optional[CodeLensOptions] = field(default=None)


@dataclass
class InitializeResult:
    capabilities: Optional[ServerCapabilities] = field(default=None)
    serverInfo: Optional[ClientInfo] = field(default=None)


@dataclass
class CodeLensParams:
    textDocument: TextDocumentIdentifier

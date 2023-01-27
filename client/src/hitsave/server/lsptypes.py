from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from hitsave.__about__ import __version__

DocumentUri = str


@dataclass
class TextDocumentIdentifier:
    uri: str
    version: Optional[int]


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
class InitializeParams:
    processId: Optional[int] = field(default=None)
    locale: Optional[str] = field(default=None)
    workspaceFolders: Optional[list[WorkspaceFolder]] = field(default=None)
    clientInfo: Optional[ClientInfo] = field(default_factory=ClientInfo)
    initializationOptions: Optional[Any] = field(default=None)
    capabilities: Optional[Any] = field(default=None)
    trace: Optional[Literal["off", "messages", "verbose"]] = field(default=None)


@dataclass
class CodeLensParams:
    textDocument: TextDocumentIdentifier

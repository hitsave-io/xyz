from dataclasses import dataclass
from typing import Optional

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
class DidChangeTextDocumentParams:
    """
    https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/#didChangeTextDocumentParams
    """

    textDocument: TextDocumentIdentifier
    contentChanges: list[TextDocumentContentChangeEvent]


@dataclass
class ClientInfo:
    name: str
    version: Optional[str]


@dataclass
class WorkspaceFolder:
    uri: DocumentUri
    name: str


@dataclass
class InitializeParams:
    clientInfo: Optional[ClientInfo]
    processId: Optional[int]
    locale: Optional[str]
    workspaceFolders: Optional[list[WorkspaceFolder]]

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import BinaryIO, Mapping
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from .diagnostics import Diagnostic, SourceSpan, TevScriptError
from .frontend_v1 import parse_v1_bytes
from .pipeline_v1 import analyze_v1_mapping
from .project_v1 import ProjectManifestV1, load_v1_project

JSONRPC_VERSION = "2.0"
LSP_POSITION_ENCODING = "utf-16"
LSP_SERVER_NAME = "TEV Script V1 canonical language server"
LSP_SERVER_VERSION = "1.0.0-candidate"


@dataclass(slots=True)
class OpenDocumentV1:
    uri: str
    text: str
    version: int | None


@dataclass(slots=True)
class LspServerV1:
    reader: BinaryIO
    writer: BinaryIO
    project_path: Path | None = None
    documents: dict[str, OpenDocumentV1] = field(default_factory=dict)
    shutdown_requested: bool = False
    exit_requested: bool = False

    def serve(self) -> int:
        while not self.exit_requested:
            message = read_lsp_message(self.reader)
            if message is None:
                return 0 if self.shutdown_requested else 1
            self.dispatch(message)
        return 0 if self.shutdown_requested else 1

    def dispatch(self, message: Mapping[str, object]) -> None:
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params")
        try:
            if method == "initialize":
                self._respond(
                    request_id,
                    {
                        "capabilities": {
                            "positionEncoding": LSP_POSITION_ENCODING,
                            "textDocumentSync": {
                                "openClose": True,
                                "change": 1,
                                "save": {"includeText": False},
                            },
                        },
                        "serverInfo": {
                            "name": LSP_SERVER_NAME,
                            "version": LSP_SERVER_VERSION,
                        },
                    },
                )
                return
            if method == "initialized":
                return
            if method == "shutdown":
                self.shutdown_requested = True
                self._respond(request_id, None)
                return
            if method == "exit":
                self.exit_requested = True
                return
            if method == "textDocument/didOpen":
                self._did_open(_object(params, "params"))
                return
            if method == "textDocument/didChange":
                self._did_change(_object(params, "params"))
                return
            if method == "textDocument/didSave":
                self._did_save(_object(params, "params"))
                return
            if method == "textDocument/didClose":
                self._did_close(_object(params, "params"))
                return
            if request_id is not None:
                self._error(request_id, -32601, f"method not supported: {method!r}")
        except TevScriptError as exc:
            if request_id is not None:
                self._error(request_id, -32602, str(exc))
            else:
                self._show_error(str(exc))
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as exc:
            if request_id is not None:
                self._error(request_id, -32602, f"{type(exc).__name__}: {exc}")
            else:
                self._show_error(f"{type(exc).__name__}: {exc}")

    def _did_open(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        text = _string(document.get("text"), "textDocument.text")
        version = _optional_int(document.get("version"), "textDocument.version")
        self.documents[uri] = OpenDocumentV1(uri, text, version)
        self._reanalyze(uri)

    def _did_change(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        version = _optional_int(document.get("version"), "textDocument.version")
        changes = params.get("contentChanges")
        if not isinstance(changes, list) or not changes:
            raise ValueError("contentChanges must contain at least one full-text change")
        latest = _object(changes[-1], "contentChanges[-1]")
        if "range" in latest:
            raise ValueError("incremental ranges are unsupported; server advertises full sync")
        text = _string(latest.get("text"), "contentChanges[-1].text")
        self.documents[uri] = OpenDocumentV1(uri, text, version)
        self._reanalyze(uri)

    def _did_save(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        if uri in self.documents:
            self._reanalyze(uri)

    def _did_close(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        self.documents.pop(uri, None)
        self._publish(uri, [])
        if self.project_path is not None:
            # Closing an unsaved overlay may reveal a different on-disk project
            # result, so recompute the project for any remaining open document.
            for remaining in self.documents:
                self._reanalyze(remaining)
                break

    def _reanalyze(self, trigger_uri: str) -> None:
        project = self._load_project_if_member(trigger_uri)
        if project is None:
            self._analyze_one(trigger_uri)
            return
        self._analyze_project(project)

    def _load_project_if_member(self, trigger_uri: str) -> ProjectManifestV1 | None:
        if self.project_path is None:
            return None
        project = load_v1_project(self.project_path)
        trigger_path = uri_to_file_path(trigger_uri)
        if trigger_path is None:
            return None
        resolved = trigger_path.resolve(strict=False)
        members = {item.path.resolve(strict=False) for item in project.sources}
        return project if resolved in members else None

    def _analyze_one(self, uri: str) -> None:
        document = self.documents.get(uri)
        if document is None:
            return
        try:
            parse_v1_bytes(uri, document.text.encode("utf-8"))
        except TevScriptError as exc:
            self._publish(uri, [diagnostic_to_lsp(exc.diagnostic, document.text)])
            return
        self._publish(uri, [])

    def _analyze_project(self, project: ProjectManifestV1) -> None:
        mapping: dict[str, bytes] = {}
        path_to_uri: dict[str, str] = {}
        path_to_text: dict[str, str] = {}

        overlays: dict[Path, OpenDocumentV1] = {}
        for document in self.documents.values():
            path = uri_to_file_path(document.uri)
            if path is not None:
                overlays[path.resolve(strict=False)] = document

        for source in project.sources:
            relative = source.relative_path
            resolved = source.path.resolve(strict=False)
            document = overlays.get(resolved)
            if document is not None:
                text = document.text
                data = text.encode("utf-8")
                uri = document.uri
            else:
                data = source.path.read_bytes()
                text = data.decode("utf-8-sig")
                uri = source.path.resolve().as_uri()
            mapping[relative] = data
            path_to_uri[relative] = uri
            path_to_text[relative] = text

        # Clear every project document first so a repaired error never leaves a
        # stale diagnostic on a different file.
        for uri in sorted(set(path_to_uri.values())):
            self._publish(uri, [])

        try:
            analyze_v1_mapping(mapping)
        except TevScriptError as exc:
            span = exc.diagnostic.span
            if span is not None and span.path in path_to_uri:
                uri = path_to_uri[span.path]
                text = path_to_text[span.path]
            else:
                uri = next(iter(path_to_uri.values()))
                text = path_to_text[next(iter(path_to_uri))]
            self._publish(uri, [diagnostic_to_lsp(exc.diagnostic, text)])

    def _respond(self, request_id: object, result: object) -> None:
        write_lsp_message(
            self.writer,
            {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result},
        )

    def _error(self, request_id: object, code: int, message: str) -> None:
        write_lsp_message(
            self.writer,
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "error": {"code": code, "message": message},
            },
        )

    def _publish(self, uri: str, diagnostics: list[dict[str, object]]) -> None:
        write_lsp_message(
            self.writer,
            {
                "jsonrpc": JSONRPC_VERSION,
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diagnostics},
            },
        )

    def _show_error(self, message: str) -> None:
        write_lsp_message(
            self.writer,
            {
                "jsonrpc": JSONRPC_VERSION,
                "method": "window/showMessage",
                "params": {"type": 1, "message": message},
            },
        )


def diagnostic_to_lsp(diagnostic: Diagnostic, text: str) -> dict[str, object]:
    span = diagnostic.span
    if span is None:
        start = {"line": 0, "character": 0}
        end = dict(start)
    else:
        start = codepoint_offset_to_lsp_position(text, span.start_offset)
        end = codepoint_offset_to_lsp_position(text, span.end_offset)
    result: dict[str, object] = {
        "range": {"start": start, "end": end},
        "severity": 1,
        "code": diagnostic.code,
        "source": "TEV Script V1",
        "message": diagnostic.message,
    }
    if diagnostic.hint:
        result["data"] = {"hint": diagnostic.hint}
    return result


def codepoint_offset_to_lsp_position(text: str, offset: int) -> dict[str, int]:
    if offset < 0 or offset > len(text):
        raise ValueError(f"source offset out of range: {offset}")
    prefix = text[:offset]
    line = prefix.count("\n")
    last_newline = prefix.rfind("\n")
    current_line = prefix[last_newline + 1 :]
    utf16_units = len(current_line.encode("utf-16-le")) // 2
    return {"line": line, "character": utf16_units}


def uri_to_file_path(uri: str) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path_text = url2pathname(unquote(parsed.path))
    if parsed.netloc:
        if os.name == "nt":
            path_text = "//" + parsed.netloc + path_text
        else:
            path_text = "/" + parsed.netloc + path_text
    return Path(path_text)


def read_lsp_message(reader: BinaryIO) -> dict[str, object] | None:
    headers: dict[str, str] = {}
    while True:
        line = reader.readline()
        if line == b"":
            return None
        if line in {b"\r\n", b"\n"}:
            break
        try:
            text = line.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("LSP headers must be ASCII") from exc
        if ":" not in text:
            raise ValueError("malformed LSP header")
        name, value = text.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    raw_length = headers.get("content-length")
    if raw_length is None:
        raise ValueError("missing Content-Length header")
    length = int(raw_length, 10)
    if length < 0 or length > 16_000_000:
        raise ValueError("invalid Content-Length")
    payload = reader.read(length)
    if len(payload) != length:
        raise ValueError("truncated LSP payload")
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("LSP JSON-RPC message must be an object")
    return value


def write_lsp_message(writer: BinaryIO, value: Mapping[str, object]) -> None:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    writer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    writer.write(payload)
    writer.flush()


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be text")
    return value


def _optional_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tev-script-v1-lsp",
        description=(
            "Thin TEV Script V1 LSP over the canonical parser/linker/static "
            "semantic pipeline. No independent language semantics are embedded."
        ),
    )
    parser.add_argument(
        "--project",
        type=Path,
        help=(
            "optional explicit TEV_SCRIPT_PROJECT_V1. When supplied, project "
            "documents receive full linker/static-semantic diagnostics; other "
            "documents receive parser diagnostics only"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    project = arguments.project
    if project is not None:
        # Validate the explicit manifest once before entering JSON-RPC. The LSP
        # reloads it on every project analysis so saved edits are observed.
        load_v1_project(project)
    server = LspServerV1(
        reader=sys.stdin.buffer,
        writer=sys.stdout.buffer,
        project_path=project,
    )
    return server.serve()


if __name__ == "__main__":
    raise SystemExit(main())

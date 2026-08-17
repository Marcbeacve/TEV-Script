from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any, BinaryIO

from .diagnostics import TevScriptError
from .json_io import load_strict_json
from .lsp_v1 import (
    codepoint_offset_to_lsp_position,
    read_lsp_message,
    uri_to_file_path,
    write_lsp_message,
)
from .program_ir_v5_total import validate_verified_proof_admission
from .source_total_core_v31 import compile_total_core_v31
from .version import CURRENT_LANGUAGE_VERSION

JSONRPC_VERSION = "2.0"
LSP_POSITION_ENCODING = "utf-16"
LSP_SERVER_NAME = "TEVScript 3.1 Total-Core language server"
LSP_SERVER_VERSION = CURRENT_LANGUAGE_VERSION

Analyzer = Callable[
    [str, Mapping[str, str], Mapping[str, Mapping[str, Any]] | None, Sequence[Any]],
    None,
]


@dataclass(slots=True)
class OpenDocumentV31:
    uri: str
    text: str
    version: int | None


@dataclass(frozen=True, slots=True)
class LspProjectV31:
    process_path: Path | None = None
    unit_paths: tuple[tuple[str, Path], ...] = ()
    effect_input_paths: tuple[tuple[str, Path], ...] = ()
    proof_admission_paths: tuple[Path, ...] = ()


def _default_analyzer(
    process_source: str,
    unit_sources: Mapping[str, str],
    effect_inputs: Mapping[str, Mapping[str, Any]] | None,
    proof_admissions: Sequence[Any],
) -> None:
    compile_total_core_v31(
        process_source,
        unit_sources=unit_sources,
        effect_inputs=effect_inputs,
        proof_admissions=proof_admissions,
    )


def _named_paths(values: Sequence[str], label: str) -> tuple[tuple[str, Path], ...]:
    result: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{label} binding must be NAME=PATH")
        name, path_text = raw.split("=", 1)
        if not name or not path_text or name in result:
            raise ValueError(f"invalid {label} binding: {raw}")
        result[name] = Path(path_text)
    return tuple(sorted(result.items()))


@dataclass(slots=True)
class LspServerV31:
    reader: BinaryIO
    writer: BinaryIO
    project: LspProjectV31 = field(default_factory=LspProjectV31)
    analyzer: Analyzer = _default_analyzer
    documents: dict[str, OpenDocumentV31] = field(default_factory=dict)
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
        except (KeyError, TypeError, ValueError, OSError, UnicodeError) as error:
            if request_id is not None:
                self._error(request_id, -32602, f"{type(error).__name__}: {error}")
            else:
                self._show_error(f"{type(error).__name__}: {error}")

    def _did_open(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        self.documents[uri] = OpenDocumentV31(
            uri,
            _string(document.get("text"), "textDocument.text"),
            _optional_int(document.get("version"), "textDocument.version"),
        )
        self._reanalyze(uri)

    def _did_change(self, params: Mapping[str, object]) -> None:
        document = _object(params.get("textDocument"), "textDocument")
        uri = _string(document.get("uri"), "textDocument.uri")
        changes = params.get("contentChanges")
        if not isinstance(changes, list) or not changes:
            raise ValueError("contentChanges must contain one full-text change")
        latest = _object(changes[-1], "contentChanges[-1]")
        if "range" in latest:
            raise ValueError("incremental ranges are unsupported")
        self.documents[uri] = OpenDocumentV31(
            uri,
            _string(latest.get("text"), "contentChanges[-1].text"),
            _optional_int(document.get("version"), "textDocument.version"),
        )
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
        if self.project.process_path is not None:
            self._reanalyze(self.project.process_path.resolve().as_uri())

    def _overlay_for_path(self, path: Path) -> OpenDocumentV31 | None:
        target = path.resolve(strict=False)
        for document in self.documents.values():
            observed = uri_to_file_path(document.uri)
            if observed is not None and observed.resolve(strict=False) == target:
                return document
        return None

    def _text_for_path(self, path: Path) -> str:
        overlay = self._overlay_for_path(path)
        if overlay is not None:
            return overlay.text
        return path.read_text(encoding="utf-8")

    def _project_inputs(
        self,
        trigger_uri: str,
    ) -> tuple[
        str,
        dict[str, str],
        dict[str, Mapping[str, Any]] | None,
        tuple[Any, ...],
        str,
    ]:
        if self.project.process_path is None:
            document = self.documents.get(trigger_uri)
            if document is None:
                raise ValueError("document is not open")
            return document.text, {}, None, (), trigger_uri

        process_path = self.project.process_path
        process_text = self._text_for_path(process_path)
        process_overlay = self._overlay_for_path(process_path)
        process_uri = (
            process_overlay.uri
            if process_overlay is not None
            else process_path.resolve().as_uri()
        )
        unit_sources = {
            name: self._text_for_path(path)
            for name, path in self.project.unit_paths
        }
        effect_inputs: dict[str, Mapping[str, Any]] = {}
        for name, path in self.project.effect_input_paths:
            value = load_strict_json(path)
            if not isinstance(value, Mapping):
                raise ValueError(f"effect input for {name} must be an object")
            effect_inputs[name] = dict(value)
        proofs: list[Any] = []
        for path in self.project.proof_admission_paths:
            value = load_strict_json(path)
            if not isinstance(value, Mapping):
                raise ValueError("proof admission must be an object")
            proofs.append(validate_verified_proof_admission(dict(value)))
        return process_text, unit_sources, effect_inputs or None, tuple(proofs), process_uri

    def _reanalyze(self, trigger_uri: str) -> None:
        try:
            process, units, effects, proofs, process_uri = self._project_inputs(trigger_uri)
            self.analyzer(process, units, effects, proofs)
        except TevScriptError as error:
            uri, text = self._diagnostic_target(trigger_uri)
            self._publish(uri, [_diagnostic_to_lsp(error, text)])
            return
        except (OSError, UnicodeError, ValueError) as error:
            uri, _ = self._diagnostic_target(trigger_uri)
            self._publish(uri, [_generic_diagnostic(str(error))])
            return

        if self.project.process_path is None:
            self._publish(trigger_uri, [])
            return
        self._publish(process_uri, [])
        for _, path in self.project.unit_paths:
            overlay = self._overlay_for_path(path)
            if overlay is not None:
                self._publish(overlay.uri, [])

    def _diagnostic_target(self, trigger_uri: str) -> tuple[str, str]:
        if self.project.process_path is None:
            document = self.documents.get(trigger_uri)
            return trigger_uri, "" if document is None else document.text
        path = self.project.process_path
        overlay = self._overlay_for_path(path)
        if overlay is not None:
            return overlay.uri, overlay.text
        try:
            return path.resolve().as_uri(), path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return trigger_uri, ""

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


def _diagnostic_to_lsp(error: TevScriptError, text: str) -> dict[str, object]:
    diagnostic = error.diagnostic
    span = diagnostic.span
    if (
        span is not None
        and isinstance(getattr(span, "start_offset", None), int)
        and isinstance(getattr(span, "end_offset", None), int)
        and 0 <= span.start_offset <= span.end_offset <= len(text)
    ):
        start = codepoint_offset_to_lsp_position(text, span.start_offset)
        end = codepoint_offset_to_lsp_position(text, span.end_offset)
    else:
        start = {"line": 0, "character": 0}
        end = dict(start)
    value: dict[str, object] = {
        "range": {"start": start, "end": end},
        "severity": 1,
        "code": diagnostic.code,
        "source": "TEVScript 3.1",
        "message": diagnostic.message,
    }
    if diagnostic.hint:
        value["data"] = {"hint": diagnostic.hint}
    return value


def _generic_diagnostic(message: str) -> dict[str, object]:
    point = {"line": 0, "character": 0}
    return {
        "range": {"start": point, "end": dict(point)},
        "severity": 1,
        "code": "TEVS_V31_LSP_PROJECT",
        "source": "TEVScript 3.1",
        "message": message,
    }


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
        prog="tev-script-lsp",
        description="TEVScript 3.1 Total-Core LSP over the canonical compiler",
    )
    parser.add_argument("--process", type=Path)
    parser.add_argument("--unit", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument(
        "--effect-input",
        action="append",
        default=[],
        metavar="NAME=JSON",
    )
    parser.add_argument(
        "--proof-admission",
        action="append",
        default=[],
        type=Path,
        metavar="JSON",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if (
        arguments.process is None
        and (arguments.unit or arguments.effect_input or arguments.proof_admission)
    ):
        raise SystemExit("--process is required with project bindings")
    project = LspProjectV31(
        process_path=arguments.process,
        unit_paths=_named_paths(arguments.unit, "unit"),
        effect_input_paths=_named_paths(arguments.effect_input, "effect-input"),
        proof_admission_paths=tuple(arguments.proof_admission),
    )
    server = LspServerV31(
        reader=sys.stdin.buffer,
        writer=sys.stdout.buffer,
        project=project,
    )
    return server.serve()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LspProjectV31",
    "LspServerV31",
    "OpenDocumentV31",
    "build_parser",
    "main",
]

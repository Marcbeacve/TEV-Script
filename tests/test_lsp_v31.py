from __future__ import annotations

import io
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.lsp_v1 import read_lsp_message
from tev_script.lsp_v31 import LspProjectV31, LspServerV31


def _open(server: LspServerV31, uri: str, text: str) -> None:
    server.dispatch(
        {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {
                    "uri": uri,
                    "text": text,
                    "version": 1,
                }
            },
        }
    )


def _messages(writer: io.BytesIO) -> list[dict[str, object]]:
    reader = io.BytesIO(writer.getvalue())
    values: list[dict[str, object]] = []
    while True:
        value = read_lsp_message(reader)
        if value is None:
            return values
        values.append(value)


def _valid_process() -> str:
    return (
        'process Demo version "3.1.0";\n'
        + "authority "
        + ("a" * 64)
        + ";\n"
        + "quantum_steps 2;\n"
        + "field actual = [];\n"
        + "label L0 = halt;\n"
        + "entry L0;\n"
    )


def test_standalone_total_core_source_uses_current_compiler() -> None:
    writer = io.BytesIO()
    server = LspServerV31(io.BytesIO(), writer)
    uri = "file:///demo.tevs"
    _open(server, uri, _valid_process())
    message = _messages(writer)[-1]
    assert message["method"] == "textDocument/publishDiagnostics"
    assert message["params"]["uri"] == uri
    assert message["params"]["diagnostics"] == []


def test_total_core_semantic_error_is_published_without_v1_fallback() -> None:
    writer = io.BytesIO()

    def analyzer(process, units, effects, proofs) -> None:
        del process, units, effects, proofs
        raise TevScriptError("TEVS_V31_TEST", "bad total-core source")

    server = LspServerV31(io.BytesIO(), writer, analyzer=analyzer)
    uri = "file:///demo.tevs"
    _open(server, uri, "invalid;")
    diagnostic = _messages(writer)[-1]["params"]["diagnostics"][0]
    assert diagnostic["code"] == "TEVS_V31_TEST"
    assert diagnostic["source"] == "TEVScript 3.1"


def test_project_unit_overlay_is_compiled_instead_of_stale_disk_bytes(
    tmp_path: Path,
) -> None:
    process = tmp_path / "main.tevs"
    unit = tmp_path / "unit.tevs"
    process.write_text(_valid_process(), encoding="utf-8")
    unit.write_text("DISK", encoding="utf-8")
    calls: list[dict[str, str]] = []

    def analyzer(process_source, units, effects, proofs) -> None:
        del process_source, effects, proofs
        calls.append(dict(units))

    writer = io.BytesIO()
    server = LspServerV31(
        io.BytesIO(),
        writer,
        project=LspProjectV31(
            process_path=process,
            unit_paths=(("Calc", unit),),
        ),
        analyzer=analyzer,
    )
    _open(server, unit.resolve().as_uri(), "OVERLAY")
    assert calls[-1] == {"Calc": "OVERLAY"}


def test_initialize_reports_current_total_core_server() -> None:
    writer = io.BytesIO()
    server = LspServerV31(io.BytesIO(), writer)
    server.dispatch({"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}})
    response = _messages(writer)[-1]
    assert response["id"] == 7
    assert response["result"]["serverInfo"]["version"] == "3.1.0"
    assert response["result"]["capabilities"]["positionEncoding"] == "utf-16"

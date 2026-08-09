from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.canonical import canonical_json
from tev_script.lsp_v1 import (
    LSP_POSITION_ENCODING,
    LspServerV1,
    codepoint_offset_to_lsp_position,
    read_lsp_message,
    write_lsp_message,
)


VALID_SOURCE = '''script Demo version "1.0.0";
entity E {
  state count: Int = 0;
  on tick {
    count = count + 1;
  }
}
'''


def framed(messages: list[dict[str, object]]) -> BytesIO:
    stream = BytesIO()
    for message in messages:
        write_lsp_message(stream, message)
    stream.seek(0)
    return stream


def read_all(stream: BytesIO) -> list[dict[str, object]]:
    stream.seek(0)
    result: list[dict[str, object]] = []
    while True:
        message = read_lsp_message(stream)
        if message is None:
            return result
        result.append(message)


class V1LspTests(unittest.TestCase):
    def test_utf16_position_conversion_is_not_codepoint_column(self) -> None:
        text = "a😀b\nçz"
        self.assertEqual(codepoint_offset_to_lsp_position(text, 0), {"line": 0, "character": 0})
        self.assertEqual(codepoint_offset_to_lsp_position(text, 1), {"line": 0, "character": 1})
        self.assertEqual(codepoint_offset_to_lsp_position(text, 2), {"line": 0, "character": 3})
        self.assertEqual(codepoint_offset_to_lsp_position(text, 3), {"line": 0, "character": 4})
        self.assertEqual(codepoint_offset_to_lsp_position(text, 4), {"line": 1, "character": 0})
        self.assertEqual(codepoint_offset_to_lsp_position(text, len(text)), {"line": 1, "character": 2})

    def test_message_framing_round_trip_preserves_unicode(self) -> None:
        expected = {"jsonrpc": "2.0", "id": 7, "result": {"text": "á😀"}}
        buffer = BytesIO()
        write_lsp_message(buffer, expected)
        raw = buffer.getvalue()
        self.assertIn(b"Content-Length:", raw)
        buffer.seek(0)
        self.assertEqual(read_lsp_message(buffer), expected)
        self.assertIsNone(read_lsp_message(buffer))

    def test_initialize_advertises_utf16_and_full_sync(self) -> None:
        reader = framed([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
            {"jsonrpc": "2.0", "method": "exit", "params": None},
        ])
        writer = BytesIO()
        server = LspServerV1(reader=reader, writer=writer)
        self.assertEqual(server.serve(), 0)
        messages = read_all(writer)
        init = messages[0]["result"]
        self.assertEqual(init["capabilities"]["positionEncoding"], LSP_POSITION_ENCODING)
        self.assertEqual(init["capabilities"]["textDocumentSync"]["change"], 1)
        self.assertIs(init["capabilities"]["textDocumentSync"]["openClose"], True)
        self.assertEqual(messages[1], {"jsonrpc": "2.0", "id": 2, "result": None})

    def test_parse_only_open_and_change_publish_and_clear_diagnostics(self) -> None:
        uri = "untitled:Demo.tevs"
        invalid = VALID_SOURCE.replace("count = count + 1;", "count = count + @;")
        reader = framed([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "languageId": "tevscript", "version": 1, "text": invalid}},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": uri, "version": 2},
                    "contentChanges": [{"text": VALID_SOURCE}],
                },
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
            {"jsonrpc": "2.0", "method": "exit", "params": None},
        ])
        writer = BytesIO()
        self.assertEqual(LspServerV1(reader=reader, writer=writer).serve(), 0)
        messages = read_all(writer)
        publishes = [item for item in messages if item.get("method") == "textDocument/publishDiagnostics"]
        self.assertEqual(len(publishes), 2)
        first = publishes[0]["params"]["diagnostics"]
        second = publishes[1]["params"]["diagnostics"]
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["code"], "TEVS_V1_LEX_UNKNOWN_CHARACTER")
        self.assertEqual(first[0]["source"], "TEV Script V1")
        self.assertEqual(second, [])

    def test_project_mode_uses_canonical_linker_not_a_second_project_parser(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tevs"
            source.write_text(
                '''script ProjectDemo version "1.0.0";
import absent;
entity E {
  state count: Int = 0;
  on tick { count = count + 1; }
}
''',
                encoding="utf-8",
            )
            project = root / "tevscript.project.json"
            project.write_text(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_PROJECT_V1",
                        "language_version": "1.0.0",
                        "sources": ["main.tevs"],
                        "default_target": "auto",
                    }
                ) + "\n",
                encoding="utf-8",
            )
            uri = source.resolve().as_uri()
            reader = framed([
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {
                    "jsonrpc": "2.0",
                    "method": "textDocument/didOpen",
                    "params": {
                        "textDocument": {
                            "uri": uri,
                            "languageId": "tevscript",
                            "version": 1,
                            "text": source.read_text(encoding="utf-8"),
                        }
                    },
                },
                {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
                {"jsonrpc": "2.0", "method": "exit", "params": None},
            ])
            writer = BytesIO()
            server = LspServerV1(reader=reader, writer=writer, project_path=project)
            self.assertEqual(server.serve(), 0)
            messages = read_all(writer)
            publishes = [item for item in messages if item.get("method") == "textDocument/publishDiagnostics"]
            self.assertGreaterEqual(len(publishes), 2)
            failures = [
                diagnostic
                for item in publishes
                for diagnostic in item["params"]["diagnostics"]
            ]
            self.assertEqual(len(failures), 1)
            self.assertTrue(str(failures[0]["code"]).startswith("TEVS_V1_LINK"))
            self.assertEqual(publishes[-1]["params"]["uri"], uri)

    def test_did_close_clears_document_diagnostics(self) -> None:
        uri = "untitled:Close.tevs"
        invalid = "script Close version \"1.0.0\"; @"
        reader = framed([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {"textDocument": {"uri": uri, "version": 1, "text": invalid}},
            },
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didClose",
                "params": {"textDocument": {"uri": uri}},
            },
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": None},
            {"jsonrpc": "2.0", "method": "exit", "params": None},
        ])
        writer = BytesIO()
        self.assertEqual(LspServerV1(reader=reader, writer=writer).serve(), 0)
        publishes = [
            item for item in read_all(writer)
            if item.get("method") == "textDocument/publishDiagnostics"
        ]
        self.assertEqual(len(publishes), 2)
        self.assertEqual(len(publishes[0]["params"]["diagnostics"]), 1)
        self.assertEqual(publishes[1]["params"]["diagnostics"], [])


if __name__ == "__main__":
    unittest.main()

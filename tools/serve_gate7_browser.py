from __future__ import annotations

import argparse
import json
import mimetypes
import os
import posixpath
import sys
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Handler(SimpleHTTPRequestHandler):
    root: Path
    witness_file: Path
    expected_tokens: dict[str, str]
    consumed: set[str]
    lock = threading.Lock()

    def translate_path(self, path: str) -> str:
        parsed = urlsplit(path)
        raw = unquote(parsed.path)
        normalized = posixpath.normpath(raw).lstrip("/")
        candidate = (self.root / normalized).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            return str(self.root / "__forbidden__")
        return str(candidate)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/__tev_gate7_witness":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            self.send_error(400)
            return
        if length < 2 or length > 2_000_000:
            self.send_error(413)
            return

        try:
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_error(400)
            return

        gate = str(payload.get("gate", ""))
        status = str(payload.get("status", ""))
        token = str(payload.get("token", ""))
        detail = str(payload.get("detail", ""))
        data = payload.get("payload", {})

        expected = self.expected_tokens.get(gate)
        if expected is None or token != expected:
            self.send_response(204)
            self.end_headers()
            return
        if status not in {"PASS", "FAIL"}:
            self.send_response(204)
            self.end_headers()
            return
        if not isinstance(data, dict):
            self.send_error(400)
            return

        with self.lock:
            if gate in self.consumed:
                self.send_response(204)
                self.end_headers()
                return
            self.consumed.add(gate)

            record = {
                "schema": "TEV_SCRIPT_GATE7_BROWSER_WITNESS_V1",
                "gate": gate,
                "status": status,
                "detail": detail,
                "payload": data,
            }
            line = json.dumps(
                record,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ) + "\n"

            self.witness_file.parent.mkdir(parents=True, exist_ok=True)
            with self.witness_file.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write("GATE7_HTTP " + (fmt % args) + "\n")
        sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--witness-file", required=True)
    parser.add_argument("--token", action="append", default=[])
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit("GATE7_SERVER_ROOT_MISSING")

    tokens: dict[str, str] = {}
    for item in args.token:
        if "=" not in item:
            raise SystemExit("GATE7_SERVER_TOKEN_FORMAT")
        gate, token = item.split("=", 1)
        if not gate or not token or gate in tokens:
            raise SystemExit("GATE7_SERVER_TOKEN_INVALID")
        tokens[gate] = token

    if not tokens:
        raise SystemExit("GATE7_SERVER_TOKEN_SET_EMPTY")

    Handler.root = root
    Handler.witness_file = Path(args.witness_file).resolve()
    Handler.expected_tokens = tokens
    Handler.consumed = set()

    mimetypes.add_type("application/wasm", ".wasm")
    mimetypes.add_type("text/javascript", ".mjs")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"GATE7_SERVER_READY=PASS port={args.port}")
    sys.stdout.flush()
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

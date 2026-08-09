from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import threading
import time
from urllib.parse import parse_qs, urlparse


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".data": "application/octet-stream",
    }

    witness_gate = ""
    witness_token = ""
    witness_file = Path("witness.jsonl")
    witness_consumed = False
    witness_lock = threading.Lock()

    def _empty_204(self) -> None:
        self.send_response(204)
        self.end_headers()

    def _witness_value(self, query: dict[str, list[str]], name: str) -> str:
        values = query.get(name, [""])
        if len(values) != 1:
            return ""
        return values[0]

    def _handle_witness(self, parsed) -> None:
        query = parse_qs(parsed.query, keep_blank_values=True)
        gate = self._witness_value(query, "gate")
        status = self._witness_value(query, "status")
        token = self._witness_value(query, "token")
        detail = self._witness_value(query, "detail")

        with Handler.witness_lock:
            if Handler.witness_consumed:
                print(
                    "WASM_HTTP_WITNESS_IGNORED reason=TOKEN_ALREADY_CONSUMED",
                    flush=True,
                )
                self._empty_204()
                return

            if gate != Handler.witness_gate:
                print(
                    f"WASM_HTTP_WITNESS_IGNORED reason=GATE_MISMATCH gate={gate}",
                    flush=True,
                )
                self._empty_204()
                return

            if not hmac.compare_digest(token, Handler.witness_token):
                print(
                    "WASM_HTTP_WITNESS_IGNORED reason=TOKEN_MISMATCH",
                    flush=True,
                )
                self._empty_204()
                return

            if status not in {"PASS", "FAIL"}:
                print(
                    f"WASM_HTTP_WITNESS_IGNORED reason=STATUS_INVALID status={status}",
                    flush=True,
                )
                self._empty_204()
                return
            if not detail:
                print(
                    "WASM_HTTP_WITNESS_IGNORED reason=DETAIL_EMPTY",
                    flush=True,
                )
                self._empty_204()
                return

            receipt = {
                "schema": "TEV_SCRIPT_BROWSER_WITNESS_V1",
                "gate": gate,
                "status": status,
                "token": token,
                "detail": detail,
                "observed_unix_ns": time.time_ns(),
            }
            line = json.dumps(
                receipt,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ) + "\n"

            Handler.witness_file.parent.mkdir(parents=True, exist_ok=True)
            with Handler.witness_file.open(
                "a", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

            Handler.witness_consumed = True
            print(
                f"WASM_HTTP_WITNESS_PERSISTED=PASS gate={gate} status={status}",
                flush=True,
            )

        self._empty_204()

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/__tev_health":
            self._empty_204()
            print("WASM_HTTP_HEALTH=PASS", flush=True)
            return

        if parsed.path == "/__tev_witness":
            self._handle_witness(parsed)
            return

        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("WASM_HTTP " + (fmt % args), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port-file", required=True)
    parser.add_argument("--witness-file", required=True)
    parser.add_argument("--witness-gate", required=True)
    parser.add_argument("--witness-token", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise RuntimeError(f"serve_root_missing:{root}")

    witness_file = Path(args.witness_file).resolve()
    if witness_file.exists():
        raise RuntimeError(f"witness_file_must_not_exist:{witness_file}")
    if not args.witness_gate:
        raise RuntimeError("witness_gate_empty")
    if not re_full_hex_128(args.witness_token):
        raise RuntimeError("witness_token_not_128_bit_hex")

    Handler.witness_gate = args.witness_gate
    Handler.witness_token = args.witness_token.lower()
    Handler.witness_file = witness_file
    Handler.witness_consumed = False

    os.chdir(root)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    Path(args.port_file).write_text(str(port), encoding="ascii")
    print(f"WASM_HTTP_PORT={port}", flush=True)
    print(f"WASM_HTTP_WITNESS_GATE={Handler.witness_gate}", flush=True)
    print("WASM_HTTP_WITNESS_FSYNC=ENABLED", flush=True)
    server.serve_forever()
    return 0


def re_full_hex_128(value: str) -> bool:
    if len(value) != 32:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in value)


if __name__ == "__main__":
    raise SystemExit(main())

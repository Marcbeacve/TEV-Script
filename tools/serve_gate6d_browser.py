from __future__ import annotations

import argparse
import hmac
import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
    }
    plan: list[dict[str, str]] = []
    index = 0
    witness_file = Path("gate6d-witness.jsonl")
    lock = threading.Lock()

    def _empty_204(self) -> None:
        self.send_response(204)
        self.end_headers()

    def _single(self, query: dict[str, list[str]], name: str) -> str:
        values = query.get(name, [""])
        return values[0] if len(values) == 1 else ""

    def _handle_witness(self, parsed) -> None:
        query = parse_qs(parsed.query, keep_blank_values=True)
        gate = self._single(query, "gate")
        status = self._single(query, "status")
        token = self._single(query, "token")
        detail = self._single(query, "detail")

        with Handler.lock:
            if Handler.index >= len(Handler.plan):
                print("GATE6D_HTTP_WITNESS_IGNORED reason=PLAN_CONSUMED", flush=True)
                self._empty_204()
                return
            expected = Handler.plan[Handler.index]
            if gate != expected["gate"]:
                print(f"GATE6D_HTTP_WITNESS_IGNORED reason=GATE_MISMATCH gate={gate}", flush=True)
                self._empty_204()
                return
            if not hmac.compare_digest(token.lower(), expected["token"]):
                print("GATE6D_HTTP_WITNESS_IGNORED reason=TOKEN_MISMATCH", flush=True)
                self._empty_204()
                return
            if status not in {"PASS", "FAIL"} or not detail:
                print("GATE6D_HTTP_WITNESS_IGNORED reason=INVALID_TERMINAL", flush=True)
                self._empty_204()
                return

            receipt = {
                "schema": "TEV_SCRIPT_GATE6D_BROWSER_WITNESS_V1",
                "sequence": Handler.index + 1,
                "gate": gate,
                "status": status,
                "token": token.lower(),
                "detail": detail,
                "observed_unix_ns": time.time_ns(),
            }
            line = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
            Handler.witness_file.parent.mkdir(parents=True, exist_ok=True)
            with Handler.witness_file.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            Handler.index += 1
            print(
                f"GATE6D_HTTP_WITNESS_PERSISTED=PASS sequence={Handler.index} gate={gate} status={status}",
                flush=True,
            )
        self._empty_204()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/__tev_health":
            self._empty_204()
            return
        if parsed.path == "/__tev_witness":
            self._handle_witness(parsed)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        print("GATE6D_HTTP " + (fmt % args), flush=True)


def token_ok(value: str) -> bool:
    return len(value) == 32 and all(c in "0123456789abcdef" for c in value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port-file", required=True)
    parser.add_argument("--witness-file", required=True)
    parser.add_argument("--plan-file", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    witness = Path(args.witness_file).resolve()
    plan_file = Path(args.plan_file).resolve()
    if not root.is_dir():
        raise RuntimeError(f"root_missing:{root}")
    if witness.exists():
        raise RuntimeError(f"witness_must_not_exist:{witness}")

    raw = json.loads(plan_file.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or len(raw) != 2:
        raise RuntimeError("plan_requires_exactly_two_phases")
    plan: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise RuntimeError(f"plan_item_invalid:{index}")
        gate = str(item.get("gate", ""))
        token = str(item.get("token", "")).lower()
        if gate not in {"gate6d-browser-fresh", "gate6d-browser-restore"}:
            raise RuntimeError(f"plan_gate_invalid:{gate}")
        if not token_ok(token):
            raise RuntimeError(f"plan_token_invalid:{index}")
        plan.append({"gate": gate, "token": token})
    if plan[0]["gate"] != "gate6d-browser-fresh" or plan[1]["gate"] != "gate6d-browser-restore":
        raise RuntimeError("plan_order_invalid")
    if hmac.compare_digest(plan[0]["token"], plan[1]["token"]):
        raise RuntimeError("plan_tokens_must_be_unique")

    Handler.plan = plan
    Handler.index = 0
    Handler.witness_file = witness
    os.chdir(root)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    Path(args.port_file).write_text(str(port), encoding="ascii")
    print(f"GATE6D_HTTP_PORT={port}", flush=True)
    print("GATE6D_HTTP_PLAN=FRESH_THEN_RESTORE", flush=True)
    print("GATE6D_HTTP_WITNESS_FSYNC=ENABLED", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

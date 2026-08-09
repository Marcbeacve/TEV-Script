from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    fixtures: Path

    def log_message(self, fmt, *args):
        print("GATE5E_HTTP " + (fmt % args), flush=True)

    def do_GET(self):
        mapping = {
            "/package1": "package1.json",
            "/package2": "package2.json",
            "/epoch2": "package_epoch2.json",
            "/tampered": "package_tampered.json",
        }

        if self.path == "/status500":
            payload = b"intentional gate5e failure"
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == "/truncated":
            data = (self.fixtures / "package1.json").read_bytes()
            data = data[: max(1, len(data) // 2)]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        name = mapping.get(self.path)
        if name is None:
            self.send_response(404)
            self.end_headers()
            return

        data = (self.fixtures / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--port-file", required=True)
    args = parser.parse_args()

    Handler.fixtures = Path(args.fixtures)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    Path(args.port_file).write_text(str(port), encoding="ascii")
    print(f"GATE5E_HTTP_SERVER_PORT={port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

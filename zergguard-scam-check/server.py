#!/usr/bin/env python3
"""Tiny HTTP server wrapping zergguard-scam-check, for iPhone Shortcut companion.

Listens on 127.0.0.1:54322 by default. POST body = the text to check.
Returns the verdict as plain text.

Run via: python3 ~/.claude/skills/zergguard-scam-check/server.py
Or as a LaunchAgent (com.matteisner.zergguard-scamserver — not yet shipped).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

CHECK = Path.home() / ".claude" / "skills" / "zergguard-scam-check" / "check.py"
DEFAULT_PORT = 54322


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(n).decode("utf-8", errors="replace")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"bad body: {e}".encode())
            return
        try:
            out = subprocess.run(
                ["python3", str(CHECK), body],
                capture_output=True, text=True, timeout=15,
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(out.stdout.encode("utf-8"))
        except subprocess.TimeoutExpired:
            self.send_response(504)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ZergGuard scam-check server. POST text to / to get a verdict.\n")

    def log_message(self, format, *args):
        return  # quiet


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-scam-server")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args(argv)
    server = HTTPServer((args.bind, args.port), Handler)
    print(f"ZergGuard scam-check server on http://{args.bind}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

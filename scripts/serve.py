#!/usr/bin/env python3
"""serve.py — static web server with live-persistence of the exclusion set.

  GET /             → serves web/index.html
  GET /tree.json    → the nested tree
  GET /api/state    → returns the saved exclusion JSON
  POST /api/state   → writes the body to index/exclude-state.json

The UI POSTs the full exclusion list on every click; the server overwrites
the file, so reload / restart never loses selections.

Usage: python3 scripts/serve.py [port]
"""
import sys
import os
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB = os.path.join(ROOT, "web")
STATE_DIR = os.path.join(ROOT, "index")
STATE = os.path.join(STATE_DIR, "exclude-state.json")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def _json(self, code, payload=b"{}"):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/state":
            data = open(STATE, "rb").read() if os.path.exists(STATE) else b"{}"
            return self._json(200, data)
        # First-run / demo: fall back to the shipped sample so the UI is never
        # blank before build-tree.py has produced a real web/tree.json.
        if self.path in ("/tree.json", "/tree.json?") and not os.path.exists(
            os.path.join(WEB, "tree.json")
        ):
            self.path = "/tree.json.example"
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/state":
            return self._json(404)
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        try:
            obj = json.loads(body)
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(STATE, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=1)
            return self._json(200, b'{"ok":true}')
        except Exception as e:
            return self._json(400, json.dumps({"ok": False, "err": str(e)}).encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 26826
    print(f"serving {WEB} on http://127.0.0.1:{port}/  state -> {STATE}")
    # Bind loopback only: the tree exposes real file paths — don't serve it
    # to the LAN. Set FO_BIND=0.0.0.0 to override for remote review.
    ThreadingHTTPServer((os.environ.get("FO_BIND", "127.0.0.1"), port), Handler).serve_forever()

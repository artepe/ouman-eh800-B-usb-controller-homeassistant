#!/usr/bin/env python3
"""Local-only, bearer-authenticated multi-site monitoring prototype.

The listener binds 127.0.0.1 ALWAYS. To reach remote technicians,
deploy an independently authenticated/TLS-protected reverse proxy or VPN.
No native HVAC control endpoints. Never route Modbus/BACnet directly
through this service.
"""
from __future__ import annotations
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import hmac
import json
import os
import re
import sys

from openhvac_lab.multisite import SiteStore

MAX_BYTES = 65536


def make_handler(store, token):
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError("OPENHVAC_LAB_TOKEN must contain at least 24 characters")
    secret = "Bearer " + token

    class Handler(BaseHTTPRequestHandler):
        server_version = "OpenHVACLab/0.5"

        def log_message(self, fmt, *args):
            # No credentials or sensitive client paths in default logs.
            pass

        # NOTE: must not be called `headers`: BaseHTTPRequestHandler stores
        # the parsed request headers in self.headers, which would shadow
        # the method and make every reply fail with TypeError.
        def _send_json_headers(self, code):
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()

        def reply(self, code, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_json_headers(code)
            self.wfile.write(body)

        def authorized(self):
            value = self.headers.get("Authorization", "")
            return hmac.compare_digest(value, secret)

        def do_GET(self):
            if not self.authorized():
                self.reply(401, {"error": "unauthorized"})
                return
            try:
                if self.path == "/health":
                    self.reply(200, {"status": "ok", "actuator_commands": 0})
                elif self.path == "/sites":
                    self.reply(200, {"sites": store.list()})
                elif re.fullmatch(r"/sites/[a-zA-Z0-9_-]{2,64}", self.path):
                    data = store.get(self.path[len("/sites/"):])
                    self.reply(200, data) if data else self.reply(404, {"error": "not_found"})
                else:
                    self.reply(404, {"error": "not_found"})
            except (ValueError, OSError):
                self.reply(400, {"error": "invalid_request"})

        def do_POST(self):
            if not self.authorized():
                self.reply(401, {"error": "unauthorized"})
                return
            if self.path != "/ingest":
                self.reply(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_BYTES:
                    self.reply(413, {"error": "invalid_size"})
                    return
                payload = json.loads(self.rfile.read(length))
                result = store.put(payload)
                self.reply(200, {"accepted": True,
                                  "site_id": result["site_id"],
                                  "actuator_commands": 0})
            except (ValueError, TypeError, json.JSONDecodeError):
                self.reply(400, {"error": "invalid_report"})
            except OSError:
                self.reply(500, {"error": "storage_error"})

    return Handler


def run(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8767)
    p.add_argument("--db", default="./openhvac_lab_sites.sqlite3")
    args = p.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        raise ValueError("Port must be in 1024-65535")
    token = os.environ.get("OPENHVAC_LAB_TOKEN", "")
    handler = make_handler(SiteStore(args.db), token)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"OpenHVAC read-only multi-site API bound to localhost:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    try:
        run()
    except (ValueError, OSError) as exc:
        print(f"OpenHVAC: {exc}", file=sys.stderr)
        sys.exit(2)

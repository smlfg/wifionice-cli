"""Offline fake of the WIFIonICE captive portal and the onboard ICE portal.

Mirrors the documented flows only: CNA API (``/cna/logon``,
``/cna/wifi/user_info``, ``/cna/logoff``) and the legacy portal
(``/de/`` with csrf cookie and ``login=true&CSRFToken=...``).
"""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

CSRF_VALUE = "test-csrf-token"

LOGIN_HTML = """<!doctype html>
<html><body>
<form id="accept" method="post" action="/de/">
  <input type="hidden" name="CSRFToken" value="{csrf}">
  <input type="submit" name="login" value="true">
</form>
</body></html>
"""

AUTH_HTML = """<!doctype html>
<html><body><a id="logout" href="/de/?logout=true">Abmelden</a></body></html>
"""


class PortalBackend:
    def __init__(self) -> None:
        self.authenticated = False
        self.cna_available = True
        self.logon_result = "success"
        self.user_info_mode = "normal"
        self.iceportal_mode = "normal"
        self.iceportal_speed = 109
        self.requests: list[dict[str, Any]] = []

    def record(self, method: str, path: str, headers: dict[str, str], body: str) -> None:
        self.requests.append(
            {"method": method, "path": path, "headers": headers, "body": body}
        )

    def paths(self) -> list[str]:
        return [f"{r['method']} {r['path']}" for r in self.requests]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server: ThreadingHTTPServer

    def log_message(self, *args: Any) -> None:
        pass

    @property
    def backend(self) -> PortalBackend:
        return self.server.backend  # type: ignore[attr-defined]

    def _send(
        self,
        status: int,
        body: str,
        content_type: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self.backend.record("GET", self.path, dict(self.headers), "")
        if self.path == "/cna/wifi/user_info":
            if not self.backend.cna_available:
                self._send(404, "no cna here", "text/plain")
                return
            if self.backend.user_info_mode == "bad_json":
                self._send(200, "{this is not json", "application/json")
                return
            if self.backend.user_info_mode == "once_503":
                self.backend.user_info_mode = "normal"
                self._send(503, "temporary outage", "text/plain")
                return
            result = {
                "authenticated": "1" if self.backend.authenticated else "0",
                "limit_mb": "200",
                "used_mb": "12",
            }
            self._send(200, json.dumps({"result": result}), "application/json")
            return
        if self.path.startswith("/de"):
            if self.backend.authenticated:
                self._send(200, AUTH_HTML, "text/html; charset=utf-8")
            else:
                self._send(
                    200,
                    LOGIN_HTML.format(csrf=CSRF_VALUE),
                    "text/html; charset=utf-8",
                    {"Set-Cookie": f"csrf={CSRF_VALUE}; Path=/"},
                )
            return
        if self.path == "/api1/rs/status":
            if self.backend.iceportal_mode == "empty":
                self._send(200, "", "application/octet-stream")
                return
            if self.backend.iceportal_mode == "bad_json":
                self._send(200, "not json", "application/json")
                return
            payload = {
                "connection": True,
                "servicelevel": "AVAILABLE_SERVICE",
                "speed": self.backend.iceportal_speed,
                "gpsStatus": "VALID",
                "latitude": 52.5161765,
                "longitude": 13.2536047,
                "wagonClass": "FIRST",
            }
            if self.backend.iceportal_mode == "no_speed":
                payload.pop("speed")
            self._send(200, json.dumps(payload), "application/json")
            return
        self._send(404, "not found", "text/plain")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        self.backend.record("POST", self.path, dict(self.headers), body)
        if self.path == "/cna/logon":
            if not self.backend.cna_available:
                self._send(404, "no cna here", "text/plain")
                return
            if self.backend.logon_result != "success":
                self._send(200, json.dumps({"result": self.backend.logon_result}), "application/json")
                return
            if not self.headers.get("X-Csrf-Token"):
                self._send(400, json.dumps({"result": "missing csrf"}), "application/json")
                return
            self.backend.authenticated = True
            self._send(200, json.dumps({"result": "success"}), "application/json")
            return
        if self.path == "/cna/logoff":
            if not self.backend.cna_available:
                self._send(404, "no cna here", "text/plain")
                return
            self.backend.authenticated = False
            self._send(200, json.dumps({"result": "success"}), "application/json")
            return
        if self.path.startswith("/de"):
            form = urllib.parse.parse_qs(body)
            if form.get("login") == ["true"] and form.get("CSRFToken") == [CSRF_VALUE]:
                self.backend.authenticated = True
                self._send(200, AUTH_HTML, "text/html; charset=utf-8")
            else:
                self._send(
                    200,
                    LOGIN_HTML.format(csrf=CSRF_VALUE),
                    "text/html; charset=utf-8",
                    {"Set-Cookie": f"csrf={CSRF_VALUE}; Path=/"},
                )
            return
        self._send(404, "not found", "text/plain")


def start_fake_portal() -> tuple[PortalBackend, str, ThreadingHTTPServer]:
    backend = PortalBackend()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.backend = backend  # type: ignore[attr-defined]
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    return backend, url, server


def dead_url() -> str:
    """Reserve a local port, then close it: connections fail fast with ECONNREFUSED."""
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"

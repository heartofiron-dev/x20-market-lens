"""Dependency-free HTTP/SSE dashboard service."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

from .realtime import RealtimeEngine


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def web_root() -> Path:
    return Path(__file__).resolve().parents[2] / "web"


class X20Handler(BaseHTTPRequestHandler):
    server_version = "X20MarketLens/0.1"

    @property
    def engine(self) -> RealtimeEngine:
        return self.server.engine  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        if self.path != "/api/events":
            super().log_message(format, *args)

    def _json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            self._json(self.engine.snapshot())
            return
        if path == "/api/health":
            self._json({"ok": True, "mode": self.engine.mode, "status": self.engine.status})
            return
        if path == "/api/events":
            self._events()
            return
        self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/symbol":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("JSON object required")
                self.engine.switch_symbol(str(payload.get("symbol", "")))
                self._json(self.engine.snapshot())
            except (ValueError, json.JSONDecodeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path != "/api/profile":
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 32_768:
                raise ValueError("payload too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            self.engine.update_profile(payload)
            self._json(self.engine.snapshot())
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _static(self, path: str) -> None:
        relative = "index.html" if path == "/" else path.lstrip("/")
        root = web_root().resolve()
        target = (root / relative).resolve()
        if root not in target.parents and target != root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", MIME_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _events(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                payload = json.dumps(self.engine.snapshot(), ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(2.0)
        except (BrokenPipeError, ConnectionResetError):
            return


class X20Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], engine: RealtimeEngine) -> None:
        super().__init__(address, X20Handler)
        self.engine = engine


def serve(host: str = "127.0.0.1", port: int = 8765, mode: str = "demo", symbol: str = "AAPL") -> None:
    engine = RealtimeEngine(mode=mode, symbol=symbol)
    engine.start()
    server = X20Server((host, port), engine)
    print(f"X20 Market Lens ({mode}, {symbol.upper()}) -> http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        server.server_close()


def start_test_server(mode: str = "demo") -> tuple[X20Server, threading.Thread]:
    engine = RealtimeEngine(mode=mode)
    engine.start()
    server = X20Server(("127.0.0.1", 0), engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread

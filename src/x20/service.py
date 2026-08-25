"""Dependency-free HTTP/SSE dashboard service with isolated user sessions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlparse

from .market_data import validate_symbol
from .profile import InvestorProfile
from .realtime import RealtimeEngine


MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}
SESSION_COOKIE = "X20SID"
MAX_BODY_BYTES = 32_768


def web_root() -> Path:
    return Path(__file__).resolve().parents[2] / "web"


class SessionCapacityError(RuntimeError):
    """Raised when a public instance has reached its configured safe capacity."""


@dataclass
class _UserSession:
    symbol: str
    profile: InvestorProfile
    last_seen: float


@dataclass
class _EngineEntry:
    engine: RealtimeEngine
    snapshot: dict[str, object]
    last_used: float


def _default_profile() -> InvestorProfile:
    return InvestorProfile(
        shares=float(os.getenv("X20_SHARES", "0")),
        entry_price=float(os.getenv("X20_ENTRY_PRICE", "0")),
        portfolio_value=float(os.getenv("X20_PORTFOLIO_VALUE", "10000")),
        risk_aversion=float(os.getenv("X20_RISK_AVERSION", "0.65")),
        max_loss_pct=float(os.getenv("X20_MAX_LOSS_PCT", "0.08")),
        horizon_days=int(os.getenv("X20_HORIZON_DAYS", "20")),
    )


class SessionManager:
    """Isolate user choices while sharing one market engine per active ticker."""

    def __init__(
        self,
        *,
        mode: str = "demo",
        symbol: str = "AAPL",
        max_sessions: int = 200,
        max_symbols: int = 12,
        session_ttl: float = 1_800.0,
        refresh_interval: float = 2.0,
        secure_cookie: bool = False,
    ) -> None:
        if max_sessions < 1 or max_symbols < 1:
            raise ValueError("max_sessions and max_symbols must be positive")
        if session_ttl < 10:
            raise ValueError("session_ttl must be at least 10 seconds")
        self.mode = mode
        self.default_symbol = validate_symbol(symbol)
        self.max_sessions = max_sessions
        self.max_symbols = max_symbols
        self.session_ttl = session_ttl
        self.refresh_interval = max(0.1, refresh_interval)
        self.secure_cookie = secure_cookie
        self._sessions: dict[str, _UserSession] = {}
        self._engines: dict[str, _EngineEntry] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._closed = False
        self._refresh_thread = threading.Thread(
            target=self._refresh_loop,
            name="x20-shared-snapshots",
            daemon=True,
        )
        self._refresh_thread.start()

    def acquire(self, candidate: str | None) -> str:
        now = time.monotonic()
        with self._lock:
            stopped = self._purge_locked(now)
            if candidate and candidate in self._sessions:
                self._sessions[candidate].last_seen = now
                sid = candidate
            else:
                if len(self._sessions) >= self.max_sessions:
                    raise SessionCapacityError("server session capacity reached; please try again later")
                sid = secrets.token_urlsafe(24)
                self._sessions[sid] = _UserSession(self.default_symbol, _default_profile(), now)
        for engine in stopped:
            engine.stop()
        return sid

    def snapshot(self, sid: str) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            session = self._require_session_locked(sid, now)
            symbol = session.symbol
            profile = session.profile
            entry = self._ensure_engine_locked(symbol, now)
            cached = deepcopy(entry.snapshot)
        if not cached:
            cached = entry.engine.snapshot()
            with self._lock:
                current = self._engines.get(symbol)
                if current is entry:
                    current.snapshot = deepcopy(cached)
        quote = cached.get("quote", {})
        price = float(quote.get("price", 0.0)) if isinstance(quote, dict) else 0.0
        model = cached.get("model", {})
        expected_return = float(model.get("expected_return_20d", 0.0)) if isinstance(model, dict) else 0.0
        uncertainty = float(model.get("uncertainty", 0.0)) if isinstance(model, dict) else 0.0
        cached["investor"] = profile.overlay(price, expected_return, uncertainty)
        cached["session"] = {
            "isolated": True,
            "storage": "server_memory",
            "expires_after_seconds": int(self.session_ttl),
        }
        return cached

    def switch_symbol(self, sid: str, symbol: str) -> dict[str, object]:
        next_symbol = validate_symbol(symbol)
        now = time.monotonic()
        stopped: list[RealtimeEngine] = []
        with self._lock:
            session = self._require_session_locked(sid, now)
            if next_symbol != session.symbol:
                active_without_current = {
                    item.symbol
                    for key, item in self._sessions.items()
                    if key != sid and now - item.last_seen <= self.session_ttl
                }
                if next_symbol not in self._engines and len(active_without_current | {next_symbol}) > self.max_symbols:
                    raise SessionCapacityError(
                        f"active ticker capacity reached ({self.max_symbols}); "
                        "try an already active ticker or retry later"
                    )
                session.symbol = next_symbol
                stopped = self._drop_unused_engines_locked(now)
                self._ensure_engine_locked(next_symbol, now)
        for engine in stopped:
            engine.stop()
        return self.snapshot(sid)

    def update_profile(self, sid: str, data: dict[str, object]) -> dict[str, object]:
        profile = InvestorProfile.from_dict(data)
        now = time.monotonic()
        with self._lock:
            session = self._require_session_locked(sid, now)
            session.profile = profile
        return self.snapshot(sid)

    def health(self) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            active = [item for item in self._sessions.values() if now - item.last_seen <= self.session_ttl]
            statuses = {symbol: entry.engine.status for symbol, entry in self._engines.items()}
            return {
                "ok": True,
                "mode": self.mode,
                "multi_user": True,
                "active_sessions": len(active),
                "active_symbols": len({item.symbol for item in active}),
                "engine_status": statuses,
            }

    def cookie_header(self, sid: str) -> str:
        parts = [
            f"{SESSION_COOKIE}={sid}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={int(self.session_ttl)}",
        ]
        if self.secure_cookie:
            parts.append("Secure")
        return "; ".join(parts)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            engines = [entry.engine for entry in self._engines.values()]
            self._engines.clear()
            self._sessions.clear()
        for engine in engines:
            engine.stop()
        if threading.current_thread() is not self._refresh_thread:
            self._refresh_thread.join(timeout=max(1.0, self.refresh_interval + 0.5))

    def _require_session_locked(self, sid: str, now: float) -> _UserSession:
        session = self._sessions.get(sid)
        if session is None:
            raise SessionCapacityError("session expired; reload the page to start a new session")
        session.last_seen = now
        return session

    def _ensure_engine_locked(self, symbol: str, now: float) -> _EngineEntry:
        entry = self._engines.get(symbol)
        if entry is not None:
            entry.last_used = now
            return entry
        active_symbols = {
            item.symbol for item in self._sessions.values() if now - item.last_seen <= self.session_ttl
        }
        if symbol not in active_symbols or len(active_symbols) > self.max_symbols:
            raise SessionCapacityError(f"active ticker capacity reached ({self.max_symbols})")
        engine = RealtimeEngine(mode=self.mode, symbol=symbol)
        engine.start()
        entry = _EngineEntry(engine=engine, snapshot={}, last_used=now)
        self._engines[symbol] = entry
        return entry

    def _purge_locked(self, now: float) -> list[RealtimeEngine]:
        expired = [sid for sid, session in self._sessions.items() if now - session.last_seen > self.session_ttl]
        for sid in expired:
            del self._sessions[sid]
        return self._drop_unused_engines_locked(now)

    def _drop_unused_engines_locked(self, now: float) -> list[RealtimeEngine]:
        active_symbols = {
            session.symbol for session in self._sessions.values() if now - session.last_seen <= self.session_ttl
        }
        unused = [symbol for symbol in self._engines if symbol not in active_symbols]
        return [self._engines.pop(symbol).engine for symbol in unused]

    def _refresh_loop(self) -> None:
        while not self._stop.wait(self.refresh_interval):
            now = time.monotonic()
            with self._lock:
                stopped = self._purge_locked(now)
                entries = list(self._engines.items())
            for engine in stopped:
                engine.stop()
            for symbol, entry in entries:
                try:
                    snapshot = entry.engine.snapshot()
                except Exception:
                    continue
                with self._lock:
                    current = self._engines.get(symbol)
                    if current is entry:
                        current.snapshot = snapshot


class X20Handler(BaseHTTPRequestHandler):
    server_version = "X20MarketLens/0.2"

    @property
    def manager(self) -> SessionManager:
        return self.server.manager  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        if self.path != "/api/events":
            super().log_message(format, *args)

    def _session_id(self) -> str:
        sid = getattr(self, "_x20_sid", "")
        if sid:
            return sid
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            candidate = cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else None
        except Exception:
            candidate = None
        sid = self.manager.acquire(candidate)
        self._x20_sid = sid
        return sid

    def _session_header(self) -> None:
        self.send_header("Set-Cookie", self.manager.cookie_header(self._session_id()))

    def _security_headers(self, *, static: bool = False) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if self.manager.secure_cookie:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        if static:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )

    def _json(self, payload: object, status: int = HTTPStatus.OK, *, session: bool = True) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        if session:
            self._session_header()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/snapshot":
                self._json(self.manager.snapshot(self._session_id()))
                return
            if path == "/api/health":
                self._json(self.manager.health(), session=False)
                return
            if path == "/api/events":
                self._events()
                return
            self._static(path)
        except SessionCapacityError as exc:
            self._json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE, session=False)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/api/symbol", "/api/profile"}:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_BODY_BYTES:
                raise ValueError("payload too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            sid = self._session_id()
            if path == "/api/symbol":
                snapshot = self.manager.switch_symbol(sid, str(payload.get("symbol", "")))
            else:
                snapshot = self.manager.update_profile(sid, payload)
            self._json(snapshot)
        except SessionCapacityError as exc:
            self._json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE, session=False)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
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
        self._security_headers(static=True)
        self._session_header()
        self.end_headers()
        self.wfile.write(body)

    def _events(self) -> None:
        sid = self._session_id()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._security_headers()
        self._session_header()
        self.end_headers()
        try:
            while True:
                payload = json.dumps(self.manager.snapshot(sid), ensure_ascii=False, separators=(",", ":"))
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                time.sleep(2.0)
        except (BrokenPipeError, ConnectionResetError, SessionCapacityError):
            return


class X20Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], manager: SessionManager) -> None:
        super().__init__(address, X20Handler)
        self.manager = manager

    def server_close(self) -> None:
        self.manager.close()
        super().server_close()


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    mode: str = "demo",
    symbol: str = "AAPL",
    *,
    max_sessions: int = 200,
    max_symbols: int | None = None,
    session_ttl: float = 1_800.0,
    secure_cookie: bool = False,
) -> None:
    symbol_limit = max_symbols if max_symbols is not None else (1 if mode == "live" else 12)
    manager = SessionManager(
        mode=mode,
        symbol=symbol,
        max_sessions=max_sessions,
        max_symbols=symbol_limit,
        session_ttl=session_ttl,
        secure_cookie=secure_cookie,
    )
    try:
        server = X20Server((host, port), manager)
    except Exception:
        manager.close()
        raise
    print(f"X20 Market Lens ({mode}, multi-user, default {symbol.upper()}) -> http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def start_test_server(
    mode: str = "demo",
    *,
    symbol: str = "AAPL",
    max_sessions: int = 20,
    max_symbols: int = 8,
) -> tuple[X20Server, threading.Thread]:
    manager = SessionManager(
        mode=mode,
        symbol=symbol,
        max_sessions=max_sessions,
        max_symbols=max_symbols,
        session_ttl=60.0,
        refresh_interval=0.2,
    )
    server = X20Server(("127.0.0.1", 0), manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread

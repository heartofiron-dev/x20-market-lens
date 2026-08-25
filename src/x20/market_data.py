"""Market-data provider interfaces and Alpaca IEX implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
import threading
from typing import Callable
from urllib.parse import quote
from urllib.request import Request, urlopen


TradeCallback = Callable[[float, float, int | None, str | None], None]
QuoteCallback = Callable[[dict[str, object]], None]
StatusCallback = Callable[[str, str], None]


class MarketDataConfigurationError(RuntimeError):
    pass


class MarketDataProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    feed: str
    coverage: str
    transport: str
    authenticated: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "feed": self.feed,
            "coverage": self.coverage,
            "transport": self.transport,
            "authenticated": self.authenticated,
        }


@dataclass(frozen=True)
class InstrumentContext:
    country: str
    exchange: str
    market_label: str
    currency: str
    regulator: str
    regulatory_url: str
    alpaca_live_supported: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "country": self.country,
            "exchange": self.exchange,
            "market_label": self.market_label,
            "currency": self.currency,
            "regulator": self.regulator,
            "regulatory_url": self.regulatory_url,
            "alpaca_live_supported": self.alpaca_live_supported,
        }


CANADIAN_SUFFIXES = {
    ".TO": "TSX",
    ".V": "TSXV",
    ".CN": "CSE",
    ".NE": "CBOE CANADA",
}


def symbol_context(symbol: str) -> InstrumentContext:
    """Describe the market convention encoded in a user-facing ticker."""
    ticker = validate_symbol(symbol)
    for suffix, exchange in CANADIAN_SUFFIXES.items():
        if ticker.endswith(suffix) and len(ticker) > len(suffix):
            return InstrumentContext(
                country="CA",
                exchange=exchange,
                market_label="CANADIAN EQUITY",
                currency="CAD",
                regulator="SEDAR+",
                regulatory_url="https://www.sedarplus.ca/landingpage/",
                alpaca_live_supported=False,
            )
    return InstrumentContext(
        country="US",
        exchange="US",
        market_label="US EQUITY",
        currency="USD",
        regulator="SEC",
        regulatory_url=f"https://www.sec.gov/edgar/search/#/q={quote(ticker)}",
        alpaca_live_supported=True,
    )


class AlpacaIEXFeed:
    """Authenticated event-driven stock feed from Alpaca's free IEX stream."""

    websocket_url = "wss://stream.data.alpaca.markets/v2/iex"
    rest_base = "https://data.alpaca.markets"

    def __init__(
        self,
        symbol: str,
        on_trade: TradeCallback,
        on_quote: QuoteCallback,
        on_status: StatusCallback,
        *,
        key_id: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self.symbol = validate_symbol(symbol)
        context = symbol_context(self.symbol)
        if not context.alpaca_live_supported:
            raise MarketDataConfigurationError(
                f"Alpaca IEX live mode does not cover {context.exchange} symbol {self.symbol}; "
                "Canadian symbols currently run in demo mode until a licensed TSX provider is configured"
            )
        self.on_trade = on_trade
        self.on_quote = on_quote
        self.on_status = on_status
        self.key_id = (key_id or os.getenv("APCA_API_KEY_ID", "")).strip()
        self.secret_key = (secret_key or os.getenv("APCA_API_SECRET_KEY", "")).strip()
        if not self.key_id or not self.secret_key:
            raise MarketDataConfigurationError(
                "Alpaca IEX requires APCA_API_KEY_ID and APCA_API_SECRET_KEY in the local environment"
            )
        self._socket: object | None = None
        self._socket_lock = threading.Lock()

    @property
    def identity(self) -> ProviderIdentity:
        return ProviderIdentity(
            provider="alpaca",
            feed="iex",
            coverage="IEX exchange only; not consolidated SIP",
            transport="REST bootstrap + WebSocket events",
            authenticated=True,
        )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.key_id,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
            "User-Agent": "X20-Market-Lens/0.2",
        }

    def _rest_json(self, path: str) -> object:
        request = Request(f"{self.rest_base}{path}", headers=self.headers)
        with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Alpaca host
            return json.load(response)

    def bootstrap(self) -> dict[str, object]:
        """Validate credentials/feed access and return the latest real snapshot."""
        raw = self._rest_json(f"/v2/stocks/{quote(self.symbol)}/snapshot?feed=iex")
        if not isinstance(raw, dict):
            raise MarketDataProtocolError("Alpaca snapshot was not a JSON object")
        latest_trade = raw.get("latestTrade") or raw.get("latest_trade") or {}
        minute_bar = raw.get("minuteBar") or raw.get("minute_bar") or {}
        daily_bar = raw.get("dailyBar") or raw.get("daily_bar") or {}
        price = _number(latest_trade, "p", "price") or _number(minute_bar, "c", "close")
        timestamp = _text(latest_trade, "t", "timestamp") or _text(minute_bar, "t", "timestamp")
        volume = _number(minute_bar, "v", "volume") or 0.0
        if not price:
            raise MarketDataProtocolError(f"Alpaca returned no IEX trade/bar for {self.symbol}")
        return {
            "symbol": self.symbol,
            "price": price,
            "volume": volume,
            "timestamp": timestamp,
            "daily_bar": daily_bar,
            "raw_kind": "alpaca_iex_snapshot",
        }

    def run(self, stop: threading.Event) -> None:
        try:
            from websockets.sync.client import connect  # type: ignore[import-not-found]
        except ImportError as exc:
            raise MarketDataConfigurationError("Install live support with: python -m pip install -e .[live]") from exc

        self.on_status("connecting", "opening Alpaca IEX WebSocket")
        with connect(self.websocket_url, open_timeout=15, close_timeout=5) as socket:
            with self._socket_lock:
                self._socket = socket
            self.on_status("connected", "WebSocket transport connected")
            socket.send(json.dumps({"action": "auth", "key": self.key_id, "secret": self.secret_key}))
            authenticated = False
            subscribed = False
            while not stop.is_set():
                try:
                    raw = socket.recv(timeout=5)
                except TimeoutError:
                    continue
                events = json.loads(raw)
                if not isinstance(events, list):
                    raise MarketDataProtocolError("Alpaca WebSocket frame was not an event array")
                for event in events:
                    kind = event.get("T")
                    if kind == "error":
                        raise MarketDataProtocolError(f"Alpaca error {event.get('code')}: {event.get('msg')}")
                    if kind == "success" and event.get("msg") == "authenticated":
                        authenticated = True
                        self.on_status("authenticated", "Alpaca credentials accepted")
                    if authenticated and not subscribed:
                        socket.send(json.dumps({
                            "action": "subscribe",
                            "trades": [self.symbol],
                            "quotes": [self.symbol],
                            "bars": [self.symbol],
                        }))
                        subscribed = True
                    if kind == "subscription":
                        self.on_status("subscribed", f"subscribed to {self.symbol} on IEX")
                    elif kind == "t" and event.get("S") == self.symbol:
                        self.on_trade(
                            float(event["p"]),
                            float(event.get("s", 0.0)),
                            iso_to_millis(event.get("t")),
                            "iex_trade",
                        )
                    elif kind == "q" and event.get("S") == self.symbol:
                        self.on_quote({
                            "bid": float(event.get("bp", 0.0)),
                            "ask": float(event.get("ap", 0.0)),
                            "bid_size": float(event.get("bs", 0.0)),
                            "ask_size": float(event.get("as", 0.0)),
                            "timestamp": event.get("t"),
                        })
                    elif kind in {"b", "u"} and event.get("S") == self.symbol:
                        self.on_trade(
                            float(event.get("c", 0.0)),
                            float(event.get("v", 0.0)),
                            iso_to_millis(event.get("t")),
                            "iex_bar",
                        )
            with self._socket_lock:
                self._socket = None

    def close(self) -> None:
        with self._socket_lock:
            socket = self._socket
        if socket is not None:
            try:
                socket.close()  # type: ignore[attr-defined]
            except Exception:
                pass


def validate_symbol(symbol: str) -> str:
    cleaned = symbol.strip().upper()
    if not cleaned or len(cleaned) > 15:
        raise ValueError("ticker must contain 1-15 characters")
    if cleaned[0].isalpha() and all(char.isalnum() or char in {".", "-"} for char in cleaned):
        return cleaned
    raise ValueError("ticker may contain letters, numbers, dot and hyphen")


def iso_to_millis(value: object) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except ValueError:
        return None


def _number(mapping: object, *keys: str) -> float:
    if not isinstance(mapping, dict):
        return 0.0
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def _text(mapping: object, *keys: str) -> str:
    if not isinstance(mapping, dict):
        return ""
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return ""

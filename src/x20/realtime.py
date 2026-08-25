"""Provider-agnostic real-time state engine."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import math
import os
import random
import statistics
import threading
from typing import Callable

from .evidence import EvidenceItem, EvidenceLedger, EvidenceTier
from .market_data import AlpacaIEXFeed, MarketDataConfigurationError, ProviderIdentity, iso_to_millis, validate_symbol
from .model import FACTOR_NAMES, QuadraticSignalModel
from .profile import InvestorProfile
from .sec_data import SecCompanyData, empty_fundamentals


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _sentiment(text: str) -> float:
    lowered = text.lower()
    positive = ("beat", "growth", "approval", "contract", "profit", "record", "success", "raise", "expand")
    negative = ("miss", "loss", "delay", "probe", "lawsuit", "crash", "risk", "cut", "plunge", "fraud")
    score = sum(word in lowered for word in positive) - sum(word in lowered for word in negative)
    return _clip(score / 3.0)


class RealtimeEngine:
    def __init__(self, mode: str = "demo", symbol: str = "AAPL", provider: str = "alpaca") -> None:
        if mode not in {"demo", "live"}:
            raise ValueError("mode must be 'demo' or 'live'")
        if provider != "alpaca":
            raise ValueError("v0.2 live provider must be 'alpaca'")
        self.mode = mode
        self.provider_name = provider
        self.symbol = validate_symbol(symbol)
        self.company = self.symbol
        self.model = QuadraticSignalModel()
        self.ledger = EvidenceLedger()
        self.profile = InvestorProfile(
            shares=float(os.getenv("X20_SHARES", "0")),
            entry_price=float(os.getenv("X20_ENTRY_PRICE", "0")),
            portfolio_value=float(os.getenv("X20_PORTFOLIO_VALUE", "10000")),
            risk_aversion=float(os.getenv("X20_RISK_AVERSION", "0.65")),
            max_loss_pct=float(os.getenv("X20_MAX_LOSS_PCT", "0.08")),
            horizon_days=int(os.getenv("X20_HORIZON_DAYS", "20")),
        )
        self.prices: deque[float] = deque(maxlen=1_200)
        self.volumes: deque[float] = deque(maxlen=1_200)
        self.times: deque[str] = deque(maxlen=1_200)
        self.quote: dict[str, object] = {"bid": 0.0, "ask": 0.0}
        self.fundamentals = empty_fundamentals(self.symbol)
        self._factor_previous: dict[str, float] | None = None
        self._factor_velocity = {name: 0.0 for name in FACTOR_NAMES}
        self._listeners: list[Callable[[], None]] = []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._feed: AlpacaIEXFeed | None = None
        self._generation = 0
        self.status = "initializing"
        self.status_detail = ""
        self.last_error = ""
        self.last_market_at = ""
        self.last_event_kind = ""
        self.provider_identity = ProviderIdentity(
            provider="simulation" if mode == "demo" else "alpaca",
            feed="synthetic" if mode == "demo" else "iex",
            coverage="simulated data" if mode == "demo" else "IEX exchange only; not consolidated SIP",
            transport="local generator" if mode == "demo" else "REST bootstrap + WebSocket events",
            authenticated=False,
        )

    def start(self) -> None:
        if self._threads:
            return
        target = self._demo_loop if self.mode == "demo" else self._alpaca_loop
        market = threading.Thread(target=target, name=f"x20-{self.mode}-market", daemon=True)
        fundamentals = threading.Thread(target=self._fundamentals_loop, name="x20-sec-fundamentals", daemon=True)
        self._threads.extend((market, fundamentals))
        market.start()
        fundamentals.start()
        if self.mode == "live":
            news = threading.Thread(target=self._news_loop, name="x20-alpaca-news", daemon=True)
            self._threads.append(news)
            news.start()

    def stop(self) -> None:
        self._stop.set()
        if self._feed:
            self._feed.close()

    def switch_symbol(self, symbol: str) -> None:
        next_symbol = validate_symbol(symbol)
        with self._lock:
            if next_symbol == self.symbol:
                return
            self.symbol = next_symbol
            self.company = next_symbol
            self._generation += 1
            self.prices.clear()
            self.volumes.clear()
            self.times.clear()
            self.quote = {"bid": 0.0, "ask": 0.0}
            self.ledger = EvidenceLedger()
            self.fundamentals = empty_fundamentals(next_symbol)
            self._factor_previous = None
            self._factor_velocity = {name: 0.0 for name in FACTOR_NAMES}
            self.status = "switching"
            self.status_detail = f"switching to {next_symbol}"
            self.last_error = ""
        if self._feed:
            self._feed.close()
        self._notify()

    def update_profile(self, data: dict[str, object]) -> None:
        with self._lock:
            self.profile = InvestorProfile.from_dict(data)
        self._notify()

    def _status(self, status: str, detail: str) -> None:
        with self._lock:
            self.status = status
            self.status_detail = detail
        self._notify()

    def _record(self, price: float, volume: float, timestamp_ms: int | None = None, event_kind: str | None = None) -> None:
        if price <= 0:
            return
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, UTC) if timestamp_ms else datetime.now(UTC)
        with self._lock:
            self.prices.append(float(price))
            self.volumes.append(max(0.0, float(volume)))
            self.times.append(timestamp.isoformat())
            self.last_market_at = timestamp.isoformat()
            self.last_event_kind = event_kind or "trade"
            if self.mode == "live" and event_kind in {"iex_trade", "iex_bar"}:
                self.status = "live"
                self.status_detail = f"receiving {event_kind} events"
            elif self.mode == "demo":
                self.status = "simulated"
                self.status_detail = "synthetic stream"
        self._notify()

    def _on_quote(self, quote: dict[str, object]) -> None:
        with self._lock:
            self.quote.update(quote)
        self._notify()

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                continue

    def _demo_loop(self) -> None:
        rng = random.Random(sum(ord(char) for char in self.symbol))
        price = 100.0
        tick = 0
        while not self._stop.is_set():
            cyclical = 0.0008 * math.sin(tick / 9.0)
            price = max(1.0, price * (1.0 + cyclical + rng.gauss(0.0, 0.0026)))
            volume = max(100.0, rng.lognormvariate(8.1, 0.55))
            self._record(price, volume, event_kind="simulated_tick")
            tick += 1
            self._stop.wait(1.0)

    def _alpaca_loop(self) -> None:
        while not self._stop.is_set():
            generation = self._generation
            symbol = self.symbol
            try:
                feed = AlpacaIEXFeed(symbol, self._record, self._on_quote, self._status)
                self._feed = feed
                self.provider_identity = feed.identity
                bootstrap = feed.bootstrap()
                self._record(float(bootstrap["price"]), float(bootstrap.get("volume", 0.0)), iso_to_millis(bootstrap.get("timestamp")), "iex_snapshot")
                self._status("snapshot_ready", f"authenticated IEX snapshot loaded for {symbol}")
                feed.run(self._stop)
            except MarketDataConfigurationError as exc:
                self.last_error = str(exc)
                self._status("configuration_error", str(exc))
                return
            except Exception as exc:
                if generation != self._generation:
                    continue
                self.last_error = str(exc)
                self._status("reconnecting", str(exc))
                self._stop.wait(5.0)
            finally:
                self._feed = None

    def _fundamentals_loop(self) -> None:
        sec = SecCompanyData()
        while not self._stop.is_set():
            generation = self._generation
            symbol = self.symbol
            try:
                fundamentals = sec.fundamentals(symbol)
                if generation == self._generation:
                    with self._lock:
                        self.fundamentals = fundamentals
                        self.company = str(fundamentals.get("company", symbol))
                    self.ledger.add(EvidenceItem(
                        title=f"{self.company} {fundamentals.get('form') or 'SEC Company Facts'}",
                        url=str(fundamentals.get("source", "")),
                        published_at=f"{fundamentals.get('filed')}T00:00:00+00:00" if fundamentals.get("filed") else datetime.now(UTC).isoformat(),
                        tier=EvidenceTier.REGULATORY,
                        sentiment=0.0,
                        claim=str(fundamentals.get("interpretation", "")),
                        source="SEC EDGAR",
                        symbol=symbol,
                    ))
                    self._notify()
            except Exception as exc:
                if generation == self._generation:
                    with self._lock:
                        self.fundamentals = empty_fundamentals(symbol, str(exc))
                    self.last_error = f"SEC: {exc}"
            for _ in range(60):
                if self._stop.wait(5.0) or generation != self._generation:
                    break

    def _news_loop(self) -> None:
        while not self._stop.is_set():
            generation = self._generation
            feed = self._feed
            symbol = self.symbol
            if feed is not None:
                try:
                    raw = feed._rest_json(f"/v1beta1/news?symbols={symbol}&limit=20&sort=desc")
                    items = raw.get("news", []) if isinstance(raw, dict) else []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        summary = str(item.get("summary", ""))
                        headline = str(item.get("headline", "Untitled"))
                        self.ledger.add(EvidenceItem(
                            title=headline,
                            url=str(item.get("url", "")),
                            published_at=str(item.get("created_at", datetime.now(UTC).isoformat())),
                            tier=EvidenceTier.SECONDARY,
                            sentiment=_sentiment(f"{headline} {summary}"),
                            claim=summary[:360],
                            source=str(item.get("source", "Alpaca News")),
                            symbol=symbol,
                        ))
                    if generation == self._generation:
                        self._notify()
                except Exception as exc:
                    self.last_error = f"news: {exc}"
            for _ in range(12):
                if self._stop.wait(5.0) or generation != self._generation:
                    break

    def _market_factors(self) -> dict[str, float]:
        prices = list(self.prices)
        volumes = list(self.volumes)
        if len(prices) < 2:
            return {name: 0.0 for name in FACTOR_NAMES[:5]}
        short_base = prices[max(0, len(prices) - 16)]
        medium_base = prices[0]
        returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices)) if prices[i - 1] > 0]
        vol = statistics.pstdev(returns[-120:]) if len(returns) > 1 else 0.0
        avg_volume = statistics.fmean(volumes[-60:]) if volumes else 1.0
        volume_shock = volumes[-1] / max(1.0, avg_volume) - 1.0
        direction = 1.0 if prices[-1] >= prices[-2] else -1.0
        bid = float(self.quote.get("bid", 0.0) or 0.0)
        ask = float(self.quote.get("ask", 0.0) or 0.0)
        midpoint = (bid + ask) / 2.0 if bid and ask else prices[-1]
        microprice_signal = _clip((prices[-1] - midpoint) / max(0.01, midpoint) * 100.0)
        return {
            "short_momentum": _clip((prices[-1] / short_base - 1.0) * 18.0),
            "medium_momentum": _clip((prices[-1] / medium_base - 1.0) * 9.0),
            "realized_volatility": _clip(vol * 85.0),
            "volume_shock": _clip(volume_shock / 2.0),
            "order_flow": _clip(direction * min(1.0, volumes[-1] / max(1.0, avg_volume)) * 0.45 + microprice_signal * 0.55),
        }

    def factors(self) -> tuple[dict[str, float], dict[str, float]]:
        with self._lock:
            market = self._market_factors()
            sentiment, credibility, rumor_pressure = self.ledger.signal()
            normalized = self.fundamentals.get("normalized", {})
            normalized = normalized if isinstance(normalized, dict) else {}
            factors = {
                **market,
                "news_sentiment": _clip(sentiment),
                "news_credibility": _clip(credibility * 2.0 - 1.0),
                "rumor_pressure": _clip(rumor_pressure * 2.0),
                "revenue_growth": _clip(float(normalized.get("revenue_growth", 0.0))),
                "rd_intensity": _clip(float(normalized.get("rd_intensity", 0.0))),
                "rd_efficiency": _clip(float(normalized.get("rd_efficiency", 0.0))),
                "operating_margin": _clip(float(normalized.get("operating_margin", 0.0))),
                "operating_cash_margin": _clip(float(normalized.get("operating_cash_margin", 0.0))),
                "capex_intensity": _clip(float(normalized.get("capex_intensity", 0.0))),
                "liquidity_strength": _clip(float(normalized.get("liquidity_strength", 0.0))),
                "valuation_stretch": 0.0,
                "rate_shock": 0.0,
                "sector_relative_strength": 0.0,
                "float_unlock_pressure": 0.0,
                "event_risk": _clip(abs(sentiment) * 0.35 + rumor_pressure * 0.65),
            }
            if self._factor_previous is not None:
                self._factor_velocity = {name: _clip(factors[name] - self._factor_previous[name], -0.25, 0.25) for name in FACTOR_NAMES}
            velocity = dict(self._factor_velocity)
            self._factor_previous = dict(factors)
            return factors, velocity

    def snapshot(self) -> dict[str, object]:
        factors, velocity = self.factors()
        coverage = 0.35 + (0.35 if self.fundamentals.get("available") else 0.0) + (0.2 if self.ledger.as_list() else 0.0)
        output = self.model.evaluate(factors, velocity, data_coverage=min(0.9, coverage), history_days=max(5, len(self.prices)))
        price = self.prices[-1] if self.prices else 0.0
        stress = self.model.stress_delta(factors, {"news_sentiment": -0.45, "realized_volatility": 0.35, "float_unlock_pressure": 0.18, "event_risk": 0.20})
        profile = self.profile.overlay(price, output.expected_return_20d, output.uncertainty)
        times = list(self.times)[-120:]
        prices = list(self.prices)[-120:]
        is_simulated = self.mode == "demo"
        return {
            "symbol": self.symbol,
            "company": self.company,
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": self.mode,
            "feed_status": self.status,
            "status_detail": self.status_detail,
            "last_market_at": self.last_market_at,
            "last_event_kind": self.last_event_kind,
            "last_error": self.last_error,
            "provider": self.provider_identity.as_dict(),
            "quote": {"price": round(price, 4), "bid": round(float(self.quote.get("bid", 0.0) or 0.0), 4), "ask": round(float(self.quote.get("ask", 0.0) or 0.0), 4), "currency": "USD", "is_simulated": is_simulated, "source": "synthetic" if is_simulated else "alpaca_iex"},
            "series": [{"t": t, "p": round(p, 4)} for t, p in zip(times, prices)],
            "factors": [{"name": name, "value": round(factors[name], 5), "velocity": round(velocity[name], 6)} for name in FACTOR_NAMES],
            "model": output.as_dict(),
            "stress_test": {key: round(value, 6) for key, value in stress.items()},
            "fundamentals": self.fundamentals,
            "evidence": self.ledger.as_list(),
            "investor": profile,
            "calculus": {"surface": "z(x) = beta_0 + beta^T x + 1/2 x^T H x", "gradient": "nabla z = beta + Hx", "chain_rule": "dz/dt = nabla z dot dx/dt", "stress": "Delta z ~= nabla z dot h + 1/2 h^T H h"},
            "limits": [
                "Alpaca free IEX is a genuine live exchange feed, but it is not the consolidated US SIP.",
                "Current coefficients are transparent heuristic priors pending walk-forward calibration.",
                "Unknown valuation, rates, sector, float and event fields remain zero instead of being guessed.",
                "Output is research and risk-management information, not an order or return guarantee.",
            ],
        }

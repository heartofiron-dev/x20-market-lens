"""Generic SEC ticker resolution and Company Facts normalization."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
import os
import threading
from typing import Callable
from urllib.request import Request, urlopen

from .market_data import validate_symbol


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def _default_fetch(url: str) -> object:
    user_agent = os.getenv("SEC_USER_AGENT", "X20 Market Lens contact@example.com")
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(request, timeout=25) as response:  # noqa: S310 - fixed SEC hosts
        return json.load(response)


class SecCompanyData:
    _ticker_cache: dict[str, dict[str, str]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, fetch_json: Callable[[str], object] = _default_fetch) -> None:
        self.fetch_json = fetch_json

    def resolve(self, symbol: str) -> dict[str, str]:
        ticker = validate_symbol(symbol)
        with self._cache_lock:
            if ticker in self._ticker_cache:
                return dict(self._ticker_cache[ticker])
        raw = self.fetch_json(SEC_TICKERS_URL)
        if not isinstance(raw, dict):
            raise ValueError("SEC ticker map is unavailable")
        resolved: dict[str, dict[str, str]] = {}
        for record in raw.values():
            if not isinstance(record, dict):
                continue
            item_ticker = str(record.get("ticker", "")).upper()
            if not item_ticker:
                continue
            resolved[item_ticker] = {
                "symbol": item_ticker,
                "cik": str(record.get("cik_str", "")).zfill(10),
                "company": str(record.get("title", item_ticker)),
            }
        with self._cache_lock:
            self._ticker_cache.update(resolved)
        if ticker not in resolved:
            raise ValueError(f"{ticker} was not found in the SEC company ticker map")
        return dict(resolved[ticker])

    def fundamentals(self, symbol: str) -> dict[str, object]:
        company = self.resolve(symbol)
        raw = self.fetch_json(SEC_COMPANY_FACTS.format(cik=company["cik"]))
        if not isinstance(raw, dict):
            raise ValueError("SEC Company Facts response is unavailable")
        us_gaap = raw.get("facts", {}).get("us-gaap", {})
        if not isinstance(us_gaap, dict):
            raise ValueError("SEC Company Facts has no us-gaap facts")

        concepts = {
            "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
            "research_and_development": ("ResearchAndDevelopmentExpense",),
            "operating_income": ("OperatingIncomeLoss",),
            "net_income": ("NetIncomeLoss", "ProfitLoss"),
            "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
            "capital_expenditures": ("PaymentsToAcquirePropertyPlantAndEquipment",),
            "cash": ("CashAndCashEquivalentsAtCarryingValue",),
            "marketable_securities": ("ShortTermInvestments", "MarketableSecuritiesCurrent"),
        }
        extracted = {name: _latest_usd(us_gaap, candidates) for name, candidates in concepts.items()}
        revenue = extracted["revenue"]
        period_key = _period_key(revenue)
        for name, candidates in concepts.items():
            if name not in {"cash", "marketable_securities", "revenue"}:
                extracted[name] = _latest_usd(us_gaap, candidates, period_key=period_key)

        revenue_value = _value(revenue)
        prior_revenue = _prior_comparable(us_gaap, concepts["revenue"], revenue)
        rd = _value(extracted["research_and_development"])
        prior_rd = _prior_comparable(us_gaap, concepts["research_and_development"], extracted["research_and_development"])
        op_income = _value(extracted["operating_income"])
        net_income = _value(extracted["net_income"])
        ocf = _value(extracted["operating_cash_flow"])
        capex = abs(_value(extracted["capital_expenditures"]))
        cash = _value(extracted["cash"])
        marketables = _value(extracted["marketable_securities"])
        revenue_growth = _growth(revenue_value, prior_revenue)
        rd_growth = _growth(rd, prior_rd)
        return {
            "available": bool(revenue_value),
            "symbol": company["symbol"],
            "company": company["company"],
            "cik": company["cik"],
            "as_of": str(revenue.get("end", "")) if revenue else "",
            "period": str(revenue.get("fp", "")) if revenue else "",
            "form": str(revenue.get("form", "")) if revenue else "",
            "filed": str(revenue.get("filed", "")) if revenue else "",
            "accession": str(revenue.get("accn", "")) if revenue else "",
            "units": "USD",
            "source": _filing_url(company["cik"], revenue),
            "revenue": revenue_value,
            "revenue_prior": prior_revenue,
            "revenue_growth": revenue_growth,
            "research_and_development": rd,
            "research_and_development_prior": prior_rd,
            "rd_growth": rd_growth,
            "rd_intensity": _ratio(rd, revenue_value),
            "rd_efficiency": _bounded((revenue_growth or 0.0) - (rd_growth or 0.0), 1.0),
            "operating_income": op_income,
            "operating_margin": _ratio(op_income, revenue_value),
            "net_income": net_income,
            "operating_cash_flow": ocf,
            "operating_cash_margin": _ratio(ocf, revenue_value),
            "capital_expenditures": capex,
            "capex_intensity": _ratio(capex, revenue_value),
            "cash_and_marketables": cash + marketables,
            "liquidity_strength": math.tanh(_ratio(cash + marketables, revenue_value)),
            "interpretation": _interpret(revenue_growth, _ratio(rd, revenue_value), _ratio(op_income, revenue_value), _ratio(capex, revenue_value)),
            "normalized": {
                "revenue_growth": _bounded(revenue_growth or 0.0, 1.0),
                "rd_intensity": _bounded(_ratio(rd, revenue_value), 1.0),
                "rd_efficiency": _bounded((revenue_growth or 0.0) - (rd_growth or 0.0), 1.0),
                "operating_margin": _bounded(_ratio(op_income, revenue_value), 1.0),
                "operating_cash_margin": _bounded(_ratio(ocf, revenue_value), 1.0),
                "capex_intensity": _bounded(_ratio(capex, revenue_value), 1.0),
                "liquidity_strength": math.tanh(_ratio(cash + marketables, revenue_value)),
            },
        }


def empty_fundamentals(symbol: str, reason: str = "loading") -> dict[str, object]:
    return {
        "available": False,
        "symbol": validate_symbol(symbol),
        "company": validate_symbol(symbol),
        "as_of": "",
        "period": "",
        "form": "",
        "filed": "",
        "units": "USD",
        "source": "",
        "revenue": 0.0,
        "revenue_prior": 0.0,
        "revenue_growth": 0.0,
        "research_and_development": 0.0,
        "rd_intensity": 0.0,
        "rd_efficiency": 0.0,
        "operating_income": 0.0,
        "operating_margin": 0.0,
        "net_income": 0.0,
        "operating_cash_flow": 0.0,
        "operating_cash_margin": 0.0,
        "capital_expenditures": 0.0,
        "capex_intensity": 0.0,
        "cash_and_marketables": 0.0,
        "liquidity_strength": 0.0,
        "interpretation": f"Fundamentals unavailable: {reason}",
        "normalized": {},
    }


def _fact_entries(us_gaap: dict[str, object], candidates: tuple[str, ...]) -> list[dict[str, object]]:
    combined: list[dict[str, object]] = []
    for concept in candidates:
        fact = us_gaap.get(concept)
        if not isinstance(fact, dict):
            continue
        units = fact.get("units", {})
        if isinstance(units, dict):
            entries = units.get("USD", [])
            if isinstance(entries, list) and entries:
                combined.extend(entry for entry in entries if isinstance(entry, dict))
    return combined


def _latest_usd(
    us_gaap: dict[str, object],
    candidates: tuple[str, ...],
    *,
    period_key: tuple[str, str, str] | None = None,
) -> dict[str, object]:
    entries = [entry for entry in _fact_entries(us_gaap, candidates) if entry.get("form") in {"10-Q", "10-K", "20-F", "40-F"}]
    if period_key:
        matched = [entry for entry in entries if _period_key(entry) == period_key]
        if matched:
            entries = matched
    entries.sort(
        key=lambda item: (str(item.get("filed", "")), str(item.get("end", "")), _duration_days(item)),
        reverse=True,
    )
    return entries[0] if entries else {}


def _period_key(entry: dict[str, object]) -> tuple[str, str, str] | None:
    if not entry:
        return None
    return (str(entry.get("fy", "")), str(entry.get("fp", "")), str(entry.get("form", "")))


def _prior_comparable(us_gaap: dict[str, object], candidates: tuple[str, ...], latest: dict[str, object]) -> float:
    if not latest:
        return 0.0
    latest_fp = latest.get("fp")
    latest_form = latest.get("form")
    duration = _duration_days(latest)
    try:
        latest_end = datetime.fromisoformat(str(latest["end"]))
    except (KeyError, ValueError):
        return 0.0
    matches = []
    for entry in _fact_entries(us_gaap, candidates):
        if entry.get("fp") != latest_fp or entry.get("form") != latest_form:
            continue
        if duration and abs(_duration_days(entry) - duration) > 10:
            continue
        try:
            candidate_end = datetime.fromisoformat(str(entry["end"]))
        except (KeyError, ValueError):
            continue
        gap = (latest_end - candidate_end).days
        if 300 <= gap <= 430:
            matches.append(entry)
    matches.sort(key=lambda item: (str(item.get("end", "")), str(item.get("filed", ""))), reverse=True)
    return _value(matches[0]) if matches else 0.0


def _duration_days(entry: dict[str, object]) -> int:
    try:
        start = datetime.fromisoformat(str(entry["start"])).replace(tzinfo=UTC)
        end = datetime.fromisoformat(str(entry["end"])).replace(tzinfo=UTC)
        return (end - start).days
    except (KeyError, ValueError):
        return 0


def _value(entry: dict[str, object]) -> float:
    try:
        return float(entry.get("val", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _growth(current: float, prior: float) -> float | None:
    return current / abs(prior) - 1.0 if prior else None


def _bounded(value: float, scale: float) -> float:
    return max(-1.0, min(1.0, value / scale))


def _filing_url(cik: str, fact: dict[str, object]) -> str:
    form = str(fact.get("form", "")) if fact else ""
    suffix = f"&type={form}" if form else ""
    return f"https://www.sec.gov/edgar/browse/?CIK={cik}{suffix}"


def _interpret(revenue_growth: float | None, rd_intensity: float, operating_margin: float, capex_intensity: float) -> str:
    growth = "增长" if (revenue_growth or 0.0) > 0 else "收缩"
    profit = "盈利" if operating_margin > 0 else "经营亏损"
    return (
        f"最新可比期显示营收{growth}、{profit}；研发/营收 {rd_intensity:.1%}，"
        f"资本开支/营收 {capex_intensity:.1%}。投入规模必须和增长、现金流及后续资本回报一起判断。"
    )

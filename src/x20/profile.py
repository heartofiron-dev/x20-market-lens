"""Investor-specific overlay. This changes risk interpretation, not market facts."""

from __future__ import annotations

from dataclasses import asdict, dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class InvestorProfile:
    shares: float = 0.0
    entry_price: float = 0.0
    portfolio_value: float = 10_000.0
    risk_aversion: float = 0.65
    max_loss_pct: float = 0.08
    horizon_days: int = 20

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "InvestorProfile":
        return cls(
            shares=max(0.0, float(data.get("shares", 0))),
            entry_price=max(0.0, float(data.get("entry_price", 0))),
            portfolio_value=max(1.0, float(data.get("portfolio_value", 10_000))),
            risk_aversion=_clamp(float(data.get("risk_aversion", 0.65)), 0.0, 1.0),
            max_loss_pct=_clamp(float(data.get("max_loss_pct", 0.08)), 0.005, 0.5),
            horizon_days=max(1, min(3650, int(data.get("horizon_days", 20)))),
        )

    def overlay(self, price: float, expected_return: float, uncertainty: float) -> dict[str, object]:
        position_value = self.shares * price
        concentration = position_value / self.portfolio_value
        pnl = self.shares * (price - self.entry_price) if self.entry_price else 0.0
        downside_95 = position_value * max(0.0, 1.645 * uncertainty - expected_return)
        loss_budget = self.portfolio_value * self.max_loss_pct
        risk_load = downside_95 / loss_budget if loss_budget else 0.0
        utility = expected_return - self.risk_aversion * uncertainty - 0.35 * max(0.0, concentration - 0.20)
        if risk_load > 1.0 or concentration > 0.35:
            status = "Above personal risk budget"
        elif risk_load > 0.65 or concentration > 0.22:
            status = "Near personal risk limit"
        else:
            status = "Within personal risk budget"
        return {
            "profile": asdict(self),
            "position_value": round(position_value, 2),
            "concentration": round(concentration, 5),
            "unrealized_pnl": round(pnl, 2),
            "downside_95_amount": round(downside_95, 2),
            "loss_budget": round(loss_budget, 2),
            "risk_load": round(risk_load, 4),
            "personal_utility": round(utility, 5),
            "status": status,
            "note": "Risk-research output only; not investment advice.",
        }

"""Explainable 20-variable quadratic signal surface.

The model is intentionally transparent.  It is a research prior until it is
calibrated on out-of-sample data; it is not represented as a trained oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


FACTOR_NAMES: tuple[str, ...] = (
    "short_momentum",
    "medium_momentum",
    "realized_volatility",
    "volume_shock",
    "order_flow",
    "news_sentiment",
    "news_credibility",
    "rumor_pressure",
    "revenue_growth",
    "rd_intensity",
    "rd_efficiency",
    "operating_margin",
    "operating_cash_margin",
    "capex_intensity",
    "liquidity_strength",
    "valuation_stretch",
    "rate_shock",
    "sector_relative_strength",
    "float_unlock_pressure",
    "event_risk",
)

FACTOR_LABELS_ZH: dict[str, str] = {
    "short_momentum": "短线动量",
    "medium_momentum": "中期动量",
    "realized_volatility": "实现波动率",
    "volume_shock": "成交量异动",
    "order_flow": "订单流",
    "news_sentiment": "新闻情绪",
    "news_credibility": "新闻可信度",
    "rumor_pressure": "传闻压力",
    "revenue_growth": "营收增长",
    "rd_intensity": "研发强度",
    "rd_efficiency": "研发转化效率",
    "operating_margin": "经营利润率",
    "operating_cash_margin": "经营现金率",
    "capex_intensity": "资本开支强度",
    "liquidity_strength": "流动性实力",
    "valuation_stretch": "估值拉伸",
    "rate_shock": "利率冲击",
    "sector_relative_strength": "行业相对强度",
    "float_unlock_pressure": "解禁供给压力",
    "event_risk": "事件风险",
}


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


@dataclass(frozen=True)
class ModelOutput:
    score: float
    probability_up: float
    expected_return_20d: float
    interval_low: float
    interval_high: float
    uncertainty: float
    gradient: tuple[float, ...]
    chain_rate: float
    curvature: float
    top_sensitivities: tuple[dict[str, float | str], ...]
    model_status: str = "heuristic_prior"

    def as_dict(self) -> dict[str, object]:
        return {
            "score": round(self.score, 5),
            "probability_up": round(self.probability_up, 5),
            "expected_return_20d": round(self.expected_return_20d, 5),
            "interval_low": round(self.interval_low, 5),
            "interval_high": round(self.interval_high, 5),
            "uncertainty": round(self.uncertainty, 5),
            "gradient": [round(v, 5) for v in self.gradient],
            "chain_rate": round(self.chain_rate, 6),
            "curvature": round(self.curvature, 6),
            "top_sensitivities": list(self.top_sensitivities),
            "model_status": self.model_status,
        }


class QuadraticSignalModel:
    """A transparent quadratic response surface over the X20 state vector.

    z(x) = beta_0 + beta^T x + 1/2 x^T H x
    grad z = beta + Hx
    dz/dt = grad z dot dx/dt
    """

    def __init__(self) -> None:
        self.intercept = -0.08
        self.beta: tuple[float, ...] = (
            0.34, 0.42, -0.48, 0.16, 0.18,
            0.32, 0.14, -0.38, 0.50, 0.20,
            0.36, 0.45, 0.46, -0.42, 0.24,
            -0.56, -0.28, 0.27, -0.52, -0.37,
        )
        size = len(FACTOR_NAMES)
        h = [[0.0 for _ in range(size)] for _ in range(size)]
        self._interaction(h, "short_momentum", "volume_shock", 0.26)
        self._interaction(h, "news_sentiment", "news_credibility", 0.34)
        self._interaction(h, "news_sentiment", "rumor_pressure", -0.28)
        self._interaction(h, "revenue_growth", "operating_cash_margin", 0.30)
        self._interaction(h, "rd_intensity", "rd_efficiency", 0.38)
        self._interaction(h, "capex_intensity", "liquidity_strength", 0.22)
        self._interaction(h, "valuation_stretch", "rate_shock", -0.36)
        self._interaction(h, "float_unlock_pressure", "event_risk", -0.31)
        self._interaction(h, "medium_momentum", "sector_relative_strength", 0.20)
        # Negative diagonal curvature encodes diminishing returns / fragility.
        for name, value in {
            "short_momentum": -0.12,
            "news_sentiment": -0.10,
            "revenue_growth": -0.10,
            "rd_intensity": -0.08,
            "valuation_stretch": -0.18,
            "realized_volatility": -0.12,
        }.items():
            h[FACTOR_NAMES.index(name)][FACTOR_NAMES.index(name)] = value
        self.hessian: tuple[tuple[float, ...], ...] = tuple(tuple(row) for row in h)

    @staticmethod
    def _interaction(matrix: list[list[float]], left: str, right: str, value: float) -> None:
        i, j = FACTOR_NAMES.index(left), FACTOR_NAMES.index(right)
        matrix[i][j] = value
        matrix[j][i] = value

    @staticmethod
    def vector(factors: Mapping[str, float] | Iterable[float]) -> tuple[float, ...]:
        if isinstance(factors, Mapping):
            missing = [name for name in FACTOR_NAMES if name not in factors]
            if missing:
                raise ValueError(f"missing factors: {', '.join(missing)}")
            values = tuple(_clip(factors[name]) for name in FACTOR_NAMES)
        else:
            values = tuple(_clip(v) for v in factors)
        if len(values) != len(FACTOR_NAMES):
            raise ValueError(f"expected {len(FACTOR_NAMES)} factors, got {len(values)}")
        return values

    def gradient(self, x: Sequence[float]) -> tuple[float, ...]:
        return tuple(
            self.beta[i] + _dot(self.hessian[i], x)
            for i in range(len(FACTOR_NAMES))
        )

    def score(self, x: Sequence[float]) -> float:
        linear = _dot(self.beta, x)
        quadratic = 0.5 * sum(
            x[i] * self.hessian[i][j] * x[j]
            for i in range(len(x))
            for j in range(len(x))
        )
        return self.intercept + linear + quadratic

    def evaluate(
        self,
        factors: Mapping[str, float] | Iterable[float],
        velocity: Mapping[str, float] | Iterable[float] | None = None,
        *,
        data_coverage: float = 0.65,
        history_days: int = 73,
    ) -> ModelOutput:
        x = self.vector(factors)
        dx = self.vector(velocity or [0.0] * len(FACTOR_NAMES))
        score = self.score(x)
        grad = self.gradient(x)
        probability = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, score))))
        chain_rate = _dot(grad, dx)
        curvature = sum(
            dx[i] * self.hessian[i][j] * dx[j]
            for i in range(len(dx))
            for j in range(len(dx))
        )
        expected = 0.085 * math.tanh(score / 3.2)
        history_penalty = min(0.12, 0.65 / math.sqrt(max(5, history_days)))
        coverage_penalty = 0.09 * (1.0 - _clip(data_coverage, 0.0, 1.0))
        volatility_penalty = 0.055 * max(0.0, x[FACTOR_NAMES.index("realized_volatility")])
        uncertainty = 0.055 + history_penalty + coverage_penalty + volatility_penalty
        sensitivity = sorted(
            (
                {
                    "factor": name,
                    "label_zh": FACTOR_LABELS_ZH[name],
                    "partial": round(grad[i], 5),
                    "state": round(x[i], 5),
                    "instant_contribution": round(grad[i] * dx[i], 6),
                }
                for i, name in enumerate(FACTOR_NAMES)
            ),
            key=lambda item: abs(float(item["partial"])),
            reverse=True,
        )[:6]
        return ModelOutput(
            score=score,
            probability_up=probability,
            expected_return_20d=expected,
            interval_low=expected - 1.645 * uncertainty,
            interval_high=expected + 1.645 * uncertainty,
            uncertainty=uncertainty,
            gradient=grad,
            chain_rate=chain_rate,
            curvature=curvature,
            top_sensitivities=tuple(sensitivity),
        )

    def stress_delta(self, factors: Mapping[str, float], shock: Mapping[str, float]) -> dict[str, float]:
        """Second-order Taylor stress: grad^T h + 1/2 h^T H h."""
        x = self.vector(factors)
        h = tuple(float(shock.get(name, 0.0)) for name in FACTOR_NAMES)
        grad = self.gradient(x)
        first = _dot(grad, h)
        second = 0.5 * sum(
            h[i] * self.hessian[i][j] * h[j]
            for i in range(len(h))
            for j in range(len(h))
        )
        return {"first_order": first, "second_order": second, "total": first + second}


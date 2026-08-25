"""Evidence provenance and rumor handling."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Iterable


class EvidenceTier(IntEnum):
    RUMOR = 1
    SECONDARY = 2
    PRIMARY = 3
    REGULATORY = 4


@dataclass(frozen=True)
class EvidenceItem:
    title: str
    url: str
    published_at: str
    tier: EvidenceTier
    sentiment: float
    claim: str
    symbol: str = ""
    contradicted: bool = False
    source: str = ""

    @property
    def credibility(self) -> float:
        base = {1: 0.16, 2: 0.48, 3: 0.78, 4: 0.96}[int(self.tier)]
        return base * (0.35 if self.contradicted else 1.0)

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["tier"] = int(self.tier)
        result["credibility"] = round(self.credibility, 3)
        return result


class EvidenceLedger:
    def __init__(self, items: Iterable[EvidenceItem] = ()) -> None:
        self._items: list[EvidenceItem] = list(items)

    def add(self, item: EvidenceItem) -> None:
        if item.url and any(existing.url == item.url for existing in self._items):
            return
        self._items.insert(0, item)
        del self._items[40:]

    def signal(self) -> tuple[float, float, float]:
        if not self._items:
            return 0.0, 0.0, 0.0
        weights = [item.credibility for item in self._items]
        total = sum(weights) or 1.0
        sentiment = sum(item.sentiment * weight for item, weight in zip(self._items, weights)) / total
        credibility = sum(weights) / len(weights)
        rumor_weight = sum(1.0 for item in self._items if item.tier == EvidenceTier.RUMOR)
        rumor_pressure = rumor_weight / len(self._items)
        return sentiment, credibility, rumor_pressure

    def as_list(self) -> list[dict[str, object]]:
        return [item.as_dict() for item in self._items]


def iso_now() -> str:
    return datetime.now(UTC).isoformat()

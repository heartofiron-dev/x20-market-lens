import unittest

from x20.evidence import EvidenceItem, EvidenceLedger, EvidenceTier
from x20.profile import InvestorProfile


class EvidenceTests(unittest.TestCase):
    def test_regulatory_outranks_rumor(self):
        regulatory = EvidenceItem("10-Q", "a", "2026-01-01", EvidenceTier.REGULATORY, 0.2, "fact")
        rumor = EvidenceItem("post", "b", "2026-01-01", EvidenceTier.RUMOR, 1.0, "claim")
        self.assertGreater(regulatory.credibility, rumor.credibility)

    def test_contradiction_reduces_credibility(self):
        normal = EvidenceItem("post", "a", "2026-01-01", EvidenceTier.SECONDARY, 0.2, "claim")
        contradicted = EvidenceItem("post", "b", "2026-01-01", EvidenceTier.SECONDARY, 0.2, "claim", contradicted=True)
        self.assertLess(contradicted.credibility, normal.credibility)

    def test_duplicate_url_is_ignored(self):
        item = EvidenceItem("10-Q", "a", "2026-01-01", EvidenceTier.REGULATORY, 0.2, "fact")
        ledger = EvidenceLedger([item])
        ledger.add(item)
        self.assertEqual(len(ledger.as_list()), 1)


class ProfileTests(unittest.TestCase):
    def test_concentration_and_loss_budget(self):
        profile = InvestorProfile(shares=10, entry_price=100, portfolio_value=5_000, max_loss_pct=0.1)
        result = profile.overlay(price=120, expected_return=0.02, uncertainty=0.1)
        self.assertAlmostEqual(result["concentration"], 0.24)
        self.assertEqual(result["loss_budget"], 500.0)
        self.assertEqual(result["unrealized_pnl"], 200.0)


if __name__ == "__main__":
    unittest.main()


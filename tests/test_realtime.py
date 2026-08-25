import unittest

from x20.model import FACTOR_NAMES
from x20.realtime import RealtimeEngine


class RealtimeEngineTests(unittest.TestCase):
    def test_snapshot_has_exactly_20_factors(self):
        engine = RealtimeEngine(mode="demo", symbol="NVDA")
        engine._record(100.0, 1_000.0)  # deterministic unit seam
        engine._record(101.0, 1_200.0)
        snapshot = engine.snapshot()
        self.assertEqual([item["name"] for item in snapshot["factors"]], list(FACTOR_NAMES))
        self.assertEqual(snapshot["quote"]["is_simulated"], True)
        self.assertEqual(snapshot["symbol"], "NVDA")
        self.assertEqual(snapshot["model"]["model_status"], "heuristic_prior")

    def test_symbol_switch_clears_old_series(self):
        engine = RealtimeEngine(mode="demo", symbol="AAPL")
        engine._record(100.0, 1000.0)
        engine.switch_symbol("msft")
        snapshot = engine.snapshot()
        self.assertEqual(snapshot["symbol"], "MSFT")
        self.assertEqual(snapshot["series"], [])

    def test_live_mode_requires_key_at_cli_boundary(self):
        engine = RealtimeEngine(mode="live")
        self.assertEqual(engine.mode, "live")


if __name__ == "__main__":
    unittest.main()

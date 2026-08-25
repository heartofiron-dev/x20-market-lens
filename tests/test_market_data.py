import unittest

from x20.market_data import AlpacaIEXFeed, MarketDataConfigurationError, iso_to_millis, validate_symbol


class MarketDataTests(unittest.TestCase):
    def test_symbol_validation_is_generic(self):
        self.assertEqual(validate_symbol(" brk.b "), "BRK.B")
        self.assertEqual(validate_symbol("SPCX"), "SPCX")
        with self.assertRaises(ValueError):
            validate_symbol("AAPL;$")

    def test_live_feed_refuses_missing_credentials(self):
        with self.assertRaises(MarketDataConfigurationError):
            AlpacaIEXFeed("AAPL", lambda *args: None, lambda *args: None, lambda *args: None, key_id="", secret_key="")

    def test_iso_timestamp_conversion(self):
        self.assertEqual(iso_to_millis("1970-01-01T00:00:01Z"), 1000)


if __name__ == "__main__":
    unittest.main()


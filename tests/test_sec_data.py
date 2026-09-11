import unittest

from x20.sec_data import SEC_COMPANY_FACTS, SEC_TICKERS_URL, SecCompanyData


class SecDataTests(unittest.TestCase):
    def test_generic_ticker_and_fact_normalization(self):
        ticker_map = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        facts = {
            "facts": {"us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                    {"val": 120.0, "start": "2026-01-01", "end": "2026-06-30", "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": "2026-08-01", "accn": "1"},
                    {"val": 100.0, "start": "2025-01-01", "end": "2025-06-30", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-08-01", "accn": "0"}
                ]}},
                "ResearchAndDevelopmentExpense": {"units": {"USD": [
                    {"val": 24.0, "start": "2026-01-01", "end": "2026-06-30", "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": "2026-08-01"},
                    {"val": 20.0, "start": "2025-01-01", "end": "2025-06-30", "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-08-01"}
                ]}},
                "OperatingIncomeLoss": {"units": {"USD": [{"val": 18.0, "start": "2026-01-01", "end": "2026-06-30", "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": "2026-08-01"}]}}
            }}
        }

        def fetch(url):
            return ticker_map if url == SEC_TICKERS_URL else facts if url == SEC_COMPANY_FACTS.format(cik="0000320193") else {}

        SecCompanyData._ticker_cache.clear()
        result = SecCompanyData(fetch).fundamentals("aapl")
        self.assertEqual(result["company"], "Apple Inc.")
        self.assertAlmostEqual(result["revenue_growth"], 0.2)
        self.assertAlmostEqual(result["rd_intensity"], 0.2)
        self.assertAlmostEqual(result["operating_margin"], 0.15)


if __name__ == "__main__":
    unittest.main()

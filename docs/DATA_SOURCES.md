# Data sources and provenance

| Domain | Provider | Transport | Cadence | v0.1 status |
|---|---|---|---|---|
| Trades, quotes, bars | Alpaca IEX | REST bootstrap + WebSocket | event-driven | implemented behind local Alpaca credentials |
| Company news | Alpaca News | REST | 60 seconds | implemented |
| Regulatory facts | SEC EDGAR Company Facts | REST | 5 minutes | generic ticker/CIK and XBRL normalization implemented |
| Audited example | SPCX 2026 Q2 10-Q | local JSON | static fixture | retained as a case study, not a runtime dependency |
| Rates | FRED | planned | 5–15 minutes | manual factor placeholder |
| Industry benchmark | Nasdaq/approved vendor | planned | 1 minute | manual factor placeholder |
| Options/short/float | licensed provider | planned | vendor-dependent | manual factor placeholder |

## Primary sources

- SEC EDGAR API documentation: <https://www.sec.gov/search-filings/edgar-application-programming-interfaces>
- Alpaca Market Data documentation: <https://docs.alpaca.markets/docs/about-market-data-api>
- Alpaca WebSocket stock stream: <https://docs.alpaca.markets/docs/real-time-stock-pricing-data>
- SPCX case-study filing: <https://www.sec.gov/Archives/edgar/data/1181412/000162828026052535/spcx-20260630.htm>

## Coverage boundary

The free Paper Trading account receives IEX data only. X20 labels the provider, feed and transport in every snapshot and does not describe IEX as consolidated SIP coverage. Missing sources remain neutral/unavailable rather than being guessed.

## Trust policy

1. Regulatory filing (tier 4)
2. Company/agency original statement (tier 3)
3. Identified secondary reporting (tier 2)
4. Unverified post/rumor (tier 1)

Contradicted items receive a credibility multiplier of `0.35`. A rumor can influence the rumor-pressure risk factor but cannot overwrite a verified numerical fact.

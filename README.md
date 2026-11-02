# X20 Market Lens

This is a stock research project I have been working on.

I started it because I was not satisfied with stock tools that show a few charts, collect some headlines, and then hand users an unexplained "bullish score." Stock prices respond to market data, interest rates, filings, news, sentiment, and rumors, but those inputs differ in timing and credibility. X20 brings them into one model whose inputs and reasoning can be inspected.

The project started with SPCX as a test case, but it is no longer tied to one ticker. It accepts U.S. symbols such as `AAPL`, `NVDA`, and `MSFT`. The Canadian equity demo supports `SHOP.TO`, `RY.TO`, and `TD.TO`, along with the `.V`, `.CN`, and `.NE` suffixes.

Most importantly, **X20 is a research MVP. It is not a proven return predictor, and it does not place trades.**

## Try it now

Public demo: <https://x20-market-lens-nq5d.onrender.com/>

Enter a ticker at the top of the page and click **Analyze** to switch stocks. Tickers, positions, and risk settings are isolated by browser session, so several people can test the site at the same time without overwriting one another's inputs.

If the public price display has an orange `DEMO` badge, the data is simulated. The price moves, but it does not represent actual exchange trades and will not automatically become live when the market opens.

The current public version can:

- switch between supported U.S. and Canadian stock symbols;
- continuously update the price chart and 20 model inputs;
- show the gradient, chain-rule rate of change, and a second-order stress test;
- calculate personal risk from share count, entry price, portfolio value, and loss tolerance;
- attempt to load SEC Company Facts for U.S. equities;
- recognize Canadian symbols as CAD and point users to SEDAR+ without pretending SEC data is available.

The public deployment currently supports up to 200 active browser sessions and 12 active stock symbols. Sessions disappear when the free Render instance sleeps or restarts. This deployment is intended for testing, not as a persistent account system.

## Running with live market data

Live market data is currently available only in the local secure mode using Alpaca Paper Trading. Install and start it with:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[live]"
.\.venv\Scripts\python.exe .\scripts\browser_credentials.py
```

Open <http://127.0.0.1:8764>, then enter an Alpaca Paper Trading Key and Secret.

The credentials exist only in the memory of the current process. They are not written to project files, exposed to browser JavaScript, or returned by the API. Live mode first loads the latest Alpaca snapshot and then connects to the IEX WebSocket for trades, quotes, and bars.

Two limitations are important:

- Alpaca's free market data comes from IEX, not the consolidated SIP covering all U.S. exchanges;
- Alpaca IEX does not provide TSX data, so Canadian symbols remain in `DEMO` mode. The program explicitly refuses to present symbols such as `SHOP.TO` as live Alpaca data.

Showing live market data to multiple public users would also require the appropriate display or redistribution rights. Until that is resolved, I will not place a personal Alpaca key on Render or label simulated prices as live prices.

To run the simulated version locally:

```powershell
$env:PYTHONPATH = "src"
python -m x20 serve --demo
```

Then open <http://127.0.0.1:8765>.

## Why multivariable calculus is part of the project

The calculus formulas are not there as decoration. X20 is built around a 20-dimensional quadratic response surface:

```text
z(x) = β₀ + βᵀx + ½xᵀHx
P(up | x) = sigmoid(z)
```

Here, `x` contains 20 normalized market-state variables.

- `∇z = β + Hx` is the gradient. It shows which small change would have the greatest local effect on the model output.
- `dz/dt = ∇z · dx/dt` applies the chain rule. It combines the current rate of change of every input to show which direction the model is moving.
- `H` is the Hessian. It represents second-order interactions between variables. For example, the same positive news should not have the same effect when source credibility is high and when it is low.
- `Δz ≈ ∇z·h + ½hᵀHh` is the second-order stress approximation. It estimates whether bad news, higher volatility, and supply pressure reinforce one another when they occur together.

The implementation is in [`src/x20/model.py`](src/x20/model.py). A fuller derivation and finite-difference verification are in [`docs/MATH.md`](docs/MATH.md).

## The 20 model inputs

The current state vector includes:

- market data: short-term momentum, medium-term momentum, realized volatility, volume shock, and order flow;
- information: news sentiment, news credibility, and rumor pressure;
- fundamentals: revenue growth, R&D intensity, R&D efficiency, operating margin, operating cash margin, capital expenditure intensity, and liquidity strength;
- environment and supply: valuation stretch, rate shock, sector-relative strength, float-unlock pressure, and event risk.

Missing data is not replaced with invented values. Inputs such as valuation, rates, sector strength, and unlock pressure remain neutral when no reliable source is available. Rumors can only affect `rumor_pressure`; they are not promoted to fundamental facts without confirmation from a regulatory filing or the company itself.

## The fundamentals I want to examine

Simply comparing which company spends more on R&D can be misleading. Higher spending does not prove that the research is effective or that the valuation is reasonable. The model therefore considers R&D spending alongside revenue growth, margins, operating cash flow, and capital expenditure.

For U.S. equities, the program looks up the SEC ticker/CIK and Company Facts, then calculates:

- revenue growth;
- R&D intensity and R&D efficiency;
- operating margin and operating cash margin;
- capital expenditure intensity and liquidity strength;
- the corresponding filing form, reporting period, filing date, and original SEC link.

`data/spcx_q2_2026.json` remains in the repository as an auditable example. It is not the default stock and is not required at runtime.

SEDAR+ fundamentals for Canadian companies are not connected yet. The page reports them as unavailable instead of substituting U.S. SEC data or simulated financial figures.

## User-specific risk also matters

The same stock is not the same problem for someone with a small position and someone whose portfolio is highly concentrated. The market model and the personal-risk layer are therefore kept separate.

Users can enter their share count, average entry price, total portfolio value, maximum tolerable loss, risk aversion, and holding horizon. The system then calculates position concentration, unrealized profit or loss, downside value implied by the model interval, and risk load relative to the user's loss budget.

These inputs exist only in the current server session. The browser receives a random `HttpOnly` session cookie, which does not contain Alpaca credentials.

## Current status

Completed:

- general ticker switching instead of a hard-coded SPCX workflow;
- local Alpaca IEX snapshots and WebSocket data;
- isolated public browser sessions and a shared per-symbol calculation cache;
- general SEC Company Facts parsing;
- Canadian symbol, exchange, CAD, and SEDAR+ boundary handling;
- the 20-factor model, gradient, Hessian, chain rule, and second-order stress testing;
- the user position and risk-budget layer;
- unit tests, concurrent browser-isolation tests, and GitHub Actions.

Not completed:

- licensing for displaying live market data publicly;
- live TSX data and SEDAR+ financial data for Canadian equities;
- purged walk-forward calibration across stocks and market regimes;
- sufficiently rigorous historical backtesting, probability calibration, slippage, and transaction-cost testing;
- options-implied volatility, FRED rates, and automatic peer benchmarks;
- persistent accounts, data-source failover, production monitoring, and a complete licensing audit.

The displayed "probability of a gain" and "20-day return interval" should therefore be treated as transparent heuristic outputs. Correct formulas do not prove that a forecast is effective, and they do not establish causation.

## Tests

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m x20 snapshot
```

The tests cover Hessian symmetry, agreement between the analytical gradient and finite differences, the chain rule, second-order stress testing, evidence credibility, the personal-risk layer, 20-factor snapshots, Canadian-symbol boundaries, and session isolation between two simultaneous browsers.

## Project structure

```text
src/x20/               Model, market data, evidence, risk layer, and HTTP/SSE service
web/                   Framework-free live dashboard
scripts/               Local credential handoff and startup scripts
data/                  Auditable example data
tests/                 Unit and integration tests
docs/                  Mathematics, architecture, data sources, and disclaimer
.github/workflows/     CI
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the detailed architecture and [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) for the acceptance criteria and roadmap.

## Disclaimer

This project is for education, research, and risk analysis. It is not investment, legal, tax, or brokerage advice. Market data, news classification, financial parsing, and model outputs can all be wrong. Do not buy or sell a security based only on this project. See [`docs/DISCLAIMER.md`](docs/DISCLAIMER.md) for the full disclaimer.

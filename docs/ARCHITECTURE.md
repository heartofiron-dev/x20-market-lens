# Architecture

```text
Ticker selected at runtime
          │
          ├─> Alpaca IEX REST snapshot + WebSocket trades/quotes/bars ─┐
          ├─> Alpaca news REST ────────────────────────────────────────┼─> timestamped evidence/state
          └─> SEC ticker/CIK + Company Facts ─────────────────────────┘              │
                                                                                     v
                                                                      X20 feature vector x(t)
                                                                                     │
                                                     z, sigmoid(z), gradient, Hessian,
                                                     chain rule and second-order stress
                                                                                     │
User position & risk budget ─────────────────────────────────────────> personal risk overlay
                                                                                     │
                                                                         atomic JSON snapshot
                                                                                     │
                                                                             SSE dashboard
```

## Timing rules

- `event_time`: when a trade/news/filing event occurred.
- `observed_at`: when X20 received it.
- `valid_from`: earliest timestamp a backtest is allowed to use it.

v0.1 keeps source publication time and feed receipt time in memory. Persistent three-clock storage is a v0.2 gate because it is essential for avoiding look-ahead leakage.

## Failure semantics

- Live mode without Alpaca credentials exits before serving.
- WebSocket failures set `reconnecting` and retain the last timestamp visibly.
- News/SEC failures are recorded in `last_error`; market streaming can continue.
- Demo mode is always labeled simulated in API and UI.
- Browser cards receive the same snapshot, preventing mixed-time calculations.
- Switching ticker invalidates the old feed generation and clears old price/evidence state before loading the new symbol.

## Security

API keys remain in the local live process and are never included in dashboard JSON. The one-time browser handoff and static server bind to `127.0.0.1`; the handoff uses a random CSRF token and `Cache-Control: no-store`. No order endpoint exists.

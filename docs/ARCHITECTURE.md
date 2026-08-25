# Architecture

```text
Browser A ─> random session A ─> ticker + InvestorProfile A ─┐
Browser B ─> random session B ─> ticker + InvestorProfile B ─┤
                                                             v
                                                  shared engine pool by ticker
                                                             │
                    market + news + SEC ─> X20 x(t), gradient, Hessian, dz/dt
                                                             │
                      session profile ─> private personal-risk overlay
                                                             │
                                             per-session JSON + SSE response
```

The pool creates one engine for each active ticker, not for each browser. A cached base
snapshot is refreshed once every two seconds, then copied before the session-specific
investor overlay is attached. This prevents one user's polling frequency or profile from
changing another user's model state.

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
- Switching ticker changes only the requesting session. An unused ticker engine is stopped and removed.
- Idle sessions expire, unused engines are reclaimed, and configured capacity is enforced with HTTP 503.

## Security

API keys remain in the local live process and are never included in dashboard JSON. The one-time browser handoff and static server bind to `127.0.0.1`; the handoff uses a random CSRF token and `Cache-Control: no-store`. Public demo sessions use a random `HttpOnly`, `SameSite=Lax`, HTTPS-only cookie and store all profile data in server memory. No order endpoint exists.

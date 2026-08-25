# Security policy

## Supported versions

Only the latest commit on `main` is supported during the research phase.

## Reporting

Do not open a public issue containing API keys, account details or portfolio data. Report a vulnerability privately through GitHub's security advisory flow when available.

## Secrets

- Keep `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` out of source control; `.env` is gitignored.
- The recommended browser credential handoff binds only to `127.0.0.1`, uses a one-time CSRF token and passes credentials to the live process without writing them to disk.
- Never embed a provider key in `web/app.js`.
- The server binds to localhost by default.
- X20 has no order-creation, order-cancellation or brokerage-account mutation endpoint.

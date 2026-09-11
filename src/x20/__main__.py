from __future__ import annotations

import argparse
import getpass
import json
import os
import sys

from .realtime import RealtimeEngine
from .service import serve


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="x20", description="X20 Market Lens")
    sub = root.add_subparsers(dest="command", required=True)
    run = sub.add_parser("serve", help="start the dashboard")
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8765)
    run.add_argument(
        "--symbol",
        default="AAPL",
        help="ticker to open; for example AAPL, or SHOP.TO in demo mode",
    )
    run.add_argument("--max-sessions", type=int, default=200, help="maximum number of browser sessions")
    run.add_argument(
        "--max-symbols",
        type=int,
        help="maximum number of ticker streams (12 in demo mode, 1 in live mode by default)",
    )
    run.add_argument("--session-ttl", type=float, default=1800, help="idle session lifetime in seconds")
    run.add_argument(
        "--secure-cookie",
        action="store_true",
        help="send the session cookie only over HTTPS",
    )
    mode = run.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="use simulated prices without an API key")
    mode.add_argument("--live", action="store_true", help="use Alpaca IEX for US prices and load SEC data and news")
    run.add_argument(
        "--prompt-credentials",
        action="store_true",
        help="ask for missing Alpaca credentials without showing them in the terminal",
    )
    snap = sub.add_parser("snapshot", help="print one model snapshot as JSON")
    snap.add_argument("--live", action="store_true")
    snap.add_argument("--symbol", default="AAPL")
    snap.add_argument(
        "--prompt-credentials",
        action="store_true",
        help="ask for missing Alpaca credentials without showing them in the terminal",
    )
    return root


def ensure_live_credentials(prompt: bool = False) -> None:
    """Check for Alpaca credentials and optionally ask for them in the terminal."""
    if os.getenv("APCA_API_KEY_ID") and os.getenv("APCA_API_SECRET_KEY"):
        return
    if not prompt:
        raise SystemExit(
            "Alpaca IEX live mode requires APCA_API_KEY_ID and APCA_API_SECRET_KEY. "
            "Set them in the local environment or add --prompt-credentials."
        )

    print("The Alpaca credentials stay in this process and are not written to disk.")
    key_id = getpass.getpass("Alpaca API Key ID (hidden): ").strip()
    secret_key = getpass.getpass("Alpaca API Secret Key (hidden): ").strip()
    if not key_id or not secret_key:
        raise SystemExit("Both Alpaca API Key ID and Secret Key are required.")
    os.environ["APCA_API_KEY_ID"] = key_id
    os.environ["APCA_API_SECRET_KEY"] = secret_key


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    mode = "live" if getattr(args, "live", False) else "demo"
    if mode == "live":
        ensure_live_credentials(getattr(args, "prompt_credentials", False))
    if args.command == "serve":
        serve(
            args.host,
            args.port,
            mode,
            args.symbol,
            max_sessions=args.max_sessions,
            max_symbols=args.max_symbols,
            session_ttl=args.session_ttl,
            secure_cookie=args.secure_cookie,
        )
        return
    engine = RealtimeEngine(mode=mode, symbol=args.symbol)
    engine.start()
    print(json.dumps(engine.snapshot(), ensure_ascii=False, indent=2))
    engine.stop()


if __name__ == "__main__":
    main()

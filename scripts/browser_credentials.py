"""Loopback-only, one-time credential handoff for starting X20 live mode."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from urllib.parse import parse_qs
from urllib.request import urlopen


HOST = "127.0.0.1"
SETUP_PORT = 8764
LIVE_PORT = 8765
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOKEN = secrets.token_urlsafe(24)
LIVE_STARTED = False
LIVE_SYMBOL = "AAPL"


def page(message: str = "", *, error: bool = False) -> bytes:
    notice = ""
    if message:
        tone = "error" if error else "success"
        notice = f'<div class="notice {tone}">{html.escape(message)}</div>'
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>X20 · Alpaca 实时连接</title>
<style>
  :root {{ color-scheme: dark; font-family: Inter, "Segoe UI", sans-serif; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #071014; color: #edf8f7; }}
  main {{ width: min(620px, calc(100% - 32px)); padding: 34px; border: 1px solid #27434a; border-radius: 18px; background: #0d1b20; box-shadow: 0 24px 80px #0008; }}
  h1 {{ margin: 0 0 10px; font-size: 27px; }}
  p {{ color: #adc2c4; line-height: 1.55; }}
  label {{ display: block; margin: 20px 0 8px; font-weight: 700; }}
  input {{ width: 100%; padding: 13px 14px; border: 1px solid #35545c; border-radius: 10px; background: #071014; color: white; font: inherit; }}
  input:focus {{ outline: 2px solid #68e7d1; border-color: transparent; }}
  button {{ margin-top: 24px; width: 100%; padding: 14px; border: 0; border-radius: 10px; background: #f6d640; color: #101510; font-weight: 800; font-size: 16px; cursor: pointer; }}
  .safe {{ padding: 12px 14px; border-radius: 10px; background: #102c29; color: #aee7da; }}
  .notice {{ margin: 15px 0; padding: 12px; border-radius: 9px; }}
  .error {{ background: #3b1820; color: #ffc2ca; }}
  .success {{ background: #123429; color: #b7f6da; }}
  small {{ display: block; margin-top: 16px; color: #82979a; }}
</style>
</head>
<body>
<main>
  <h1>连接 Alpaca Paper 实时行情</h1>
  <p>请从 Alpaca Dashboard 复制<strong>刚刚重新生成</strong>的 Key 和 Secret。不要把它们发送到聊天。</p>
  <div class="safe">仅通过 127.0.0.1 交给本机 X20 进程；不会写入文件，也不会进入 Git。</div>
  {notice}
  <form method="post" action="/start" autocomplete="off">
    <input type="hidden" name="token" value="{TOKEN}">
    <label for="key_id">Alpaca API Key ID</label>
    <input id="key_id" name="key_id" type="password" required spellcheck="false" autocomplete="off">
    <label for="secret_key">Alpaca API Secret Key</label>
    <input id="secret_key" name="secret_key" type="password" required spellcheck="false" autocomplete="off">
    <label for="symbol">启动股票代码</label>
    <input id="symbol" name="symbol" value="AAPL" maxlength="15" required spellcheck="false">
    <button type="submit">启动真实 Alpaca IEX</button>
  </form>
  <small>提交后页面会自动进入 http://127.0.0.1:8765/。</small>
</main>
</body>
</html>""".encode("utf-8")


def success_page(symbol: str) -> bytes:
    safe_symbol = html.escape(symbol)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1;url=http://{HOST}:{LIVE_PORT}/">
<title>X20 · 实时连接成功</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #071014; color: #edf8f7; font-family: Inter, "Segoe UI", sans-serif; }}
  main {{ width: min(560px, calc(100% - 32px)); padding: 36px; border: 1px solid #27584e; border-radius: 18px; background: #0d1b20; text-align: center; }}
  h1 {{ color: #7cf2d8; }}
  p {{ color: #bad0d0; line-height: 1.6; }}
  a {{ display: inline-block; margin-top: 18px; padding: 13px 22px; border-radius: 10px; background: #f6d640; color: #101510; font-weight: 800; text-decoration: none; }}
</style>
</head>
<body><main>
  <h1>Alpaca IEX 已连接</h1>
  <p>{safe_symbol} 的真实行情服务已经启动，正在进入 X20 仪表盘。</p>
  <a href="http://{HOST}:{LIVE_PORT}/">立即打开实时仪表盘</a>
</main></body>
</html>""".encode("utf-8")


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "X20CredentialSetup/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_page(self, body: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_page(success_page(LIVE_SYMBOL) if LIVE_STARTED else page())

    def do_POST(self) -> None:  # noqa: N802
        global LIVE_STARTED, LIVE_SYMBOL
        if self.path != "/start":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 8_192:
                raise ValueError("提交内容大小不正确。")
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            submitted_token = fields.get("token", [""])[0]
            if not hmac.compare_digest(submitted_token, TOKEN):
                raise ValueError("页面令牌已失效，请刷新后重试。")
            key_id = fields.get("key_id", [""])[0].strip()
            secret_key = fields.get("secret_key", [""])[0].strip()
            symbol = fields.get("symbol", ["AAPL"])[0].strip().upper()
            if not key_id or not secret_key:
                raise ValueError("Key ID 和 Secret Key 都必须填写。")
            if not symbol or len(symbol) > 15 or not all(c.isalnum() or c in ".-" for c in symbol):
                raise ValueError("股票代码格式不正确。")

            executable = PROJECT_ROOT / ".venv" / "Scripts" / "x20.exe"
            if not executable.is_file():
                raise ValueError("项目虚拟环境不存在。")
            child_env = os.environ.copy()
            child_env["APCA_API_KEY_ID"] = key_id
            child_env["APCA_API_SECRET_KEY"] = secret_key
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            process = subprocess.Popen(
                [str(executable), "serve", "--live", "--symbol", symbol, "--port", str(LIVE_PORT)],
                cwd=PROJECT_ROOT,
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            del key_id, secret_key, child_env, fields

            deadline = time.monotonic() + 15
            last_status = "本地实时服务尚未响应"
            while time.monotonic() < deadline:
                try:
                    with urlopen(f"http://{HOST}:{LIVE_PORT}/api/snapshot", timeout=0.5) as response:
                        snapshot = json.load(response)
                        feed_status = str(snapshot.get("feed_status", "unknown"))
                        status_detail = str(snapshot.get("status_detail", "")).strip()
                        last_error = str(snapshot.get("last_error", "")).strip()
                        last_status = ": ".join(
                            part for part in (feed_status, status_detail or last_error) if part
                        )
                        ready = (
                            response.status == HTTPStatus.OK
                            and snapshot.get("mode") == "live"
                            and feed_status
                            in {"snapshot_ready", "connecting", "connected", "authenticated", "subscribed", "live"}
                        )
                        if ready:
                            LIVE_STARTED = True
                            LIVE_SYMBOL = symbol
                            self.send_page(success_page(symbol))
                            return
                except OSError:
                    time.sleep(0.2)
            process.terminate()
            raise ValueError(f"实时服务没有通过 Alpaca 验证。本地状态：{last_status}")
        except (UnicodeDecodeError, ValueError) as exc:
            self.send_page(page(str(exc), error=True), HTTPStatus.BAD_REQUEST)


def main() -> None:
    server = ThreadingHTTPServer((HOST, SETUP_PORT), SetupHandler)
    print(f"X20 secure local credential page -> http://{HOST}:{SETUP_PORT}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

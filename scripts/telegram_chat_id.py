"""Run locally after sending /start to your bot. Do not run in public Actions logs."""
import os
import requests

token = os.environ.get("TELEGRAM_BOT_TOKEN","")
if not token:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN privately first")
try:
    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",timeout=20)
    payload = response.json()
    if response.status_code!=200 or payload.get("ok") is not True:
        raise ValueError()
    ids = {str(u["message"]["chat"]["id"]) for u in payload["result"] if "message" in u}
    print("Chat ID(s): "+", ".join(sorted(ids)) if ids else "No messages. Send /start to the bot first.")
except (requests.RequestException,ValueError,KeyError,TypeError):
    raise SystemExit("Telegram lookup failed. Check the token privately; no raw error logged.") from None

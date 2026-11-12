"""Notification-only cloud entry point using the upstream CAPTCHA workflow."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from lib import config, extractors
from lib.appointment_handler import AppointmentHandler

PORTAL_URL = ("https://service2.diplo.de/rktermin/extern/appointment_showMonth.do"
              "?locationCode=niko&realmId=926&categoryId=1860")


def telegram(message):
    """Check Telegram's JSON result without logging the secret-bearing URL."""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message,
                  "disable_web_page_preview": True}, timeout=30)
        if response.status_code != 200 or response.json().get("ok") is not True:
            raise RuntimeError("Telegram rejected the message; check bot token and chat ID")
    except (requests.RequestException, ValueError):
        raise RuntimeError("Telegram delivery failed") from None


def available_dates(html):
    page = BeautifulSoup(html, "html.parser")
    if page.find("input", attrs={"name": "captchaText"}):
        raise RuntimeError("The portal still shows a CAPTCHA")
    dates = set()
    for link in page.select('a[href]'):
        href = link["href"]
        if "appointment_showDay.do" not in href:
            continue
        query = parse_qs(urlparse(href).query)
        if any(query.get(key, [None])[0] != value for key, value in
               (("locationCode", "niko"), ("realmId", "926"), ("categoryId", "1860"))):
            raise RuntimeError("Portal returned a different appointment category")
        try:
            candidate = datetime.strptime(query["dateStr"][0], "%d.%m.%Y").date()
        except (KeyError, ValueError):
            raise RuntimeError("Portal returned an unreadable appointment date") from None
        if config.is_acceptable_date(candidate.month, candidate.day, candidate.year):
            dates.add(candidate)
    if dates:
        return [d.strftime("%d.%m.%Y") for d in sorted(dates)]
    text = " ".join(page.stripped_strings).lower()
    empty_markers = ("there are no appointments available", "keine termine verfügbar",
                     "keine termine zur verfügung", "keine freien termine")
    if not any(marker in text for marker in empty_markers):
        raise RuntimeError("Unrecognized portal response; availability is unknown")
    return []


def main():
    result = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "target": "niko:926:1860", "auto_book": False,
              "coverage": "current portal month"}
    exit_code = 0
    try:
        for name in ("CAPTCHA_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            if not getattr(config, name):
                raise RuntimeError(f"Missing GitHub Actions secret: {name}")
        # This entry point never calls the booking workflow or a booking method.
        config.AUTO_BOOK = False
        config.BOOKING_DRY_RUN = True
        if not AppointmentHandler(str(Path.cwd())).fetch_month_view():
            raise RuntimeError("Could not pass the portal CAPTCHA; availability is unknown")
        html = Path("target/response.html").read_text(encoding="utf-8")
        dates = available_dates(html)
        result.update(status="ok", dates=dates)
        if dates:
            telegram("Visa appointment available — North Nicosia\n" +
                     "\n".join(dates) + "\nBook manually: " + PORTAL_URL)
        if os.environ.get("VERIFY_SETUP") == "true":
            telegram("Nicosia visa monitor: setup test passed.\n"
                     "CAPTCHA accepted; current portal month checked.\n" +
                     ("Available dates: " + ", ".join(dates) if dates else "No appointments available.") +
                     "\nCloud schedule: every 30 minutes. Notifications only.")
    except Exception as error:
        # Exception text from upstream could contain sensitive request data.
        # Only our explicit operational messages are included in the result.
        message = str(error) if isinstance(error, RuntimeError) else "Unexpected check failure"
        result.update(status="failed", error=message)
        exit_code = 1
        try:
            telegram("Nicosia visa monitor failed: " + message +
                     "\nAvailability is unknown. Check GitHub Actions.")
        except RuntimeError:
            pass
    Path("result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("### Nicosia appointment check\n```json\n" +
                          json.dumps(result, indent=2) + "\n```\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

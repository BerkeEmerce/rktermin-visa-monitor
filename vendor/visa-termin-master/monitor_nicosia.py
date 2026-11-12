"""Notification-only cloud entry point using the upstream CAPTCHA workflow."""
import json
import calendar
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from lib import config, extractors
from lib.appointment_handler import AppointmentHandler
from email_alerts import send_email

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


def notify_available(dates):
    if not dates:
        return
    text = ("Visa appointment available — North Nicosia\n" +
            "\n".join(dates) + "\nBook manually: " + PORTAL_URL)
    failed = []
    for name, send in (("Telegram", telegram), ("email", send_email)):
        try:
            send(text)
        except RuntimeError:
            failed.append(name)
    if failed:
        raise RuntimeError("Appointment alert delivery failed for: " + ", ".join(failed))


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


def displayed_month(html):
    """Read the displayed heading, never infer it from the requested URL."""
    names = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
    names.update(dict(zip("januar februar märz april mai juni juli august september oktober november dezember".split(), range(1, 13))))
    found = set()
    page = BeautifulSoup(html, "html.parser")
    for heading in page.select("h1,h2,h3,h4,caption,th,.month-title,.calendar-title"):
        text = " ".join(heading.get_text(" ", strip=True).lower().split())
        numeric = re.fullmatch(r"(0?[1-9]|1[0-2])\s*/\s*(20\d{2})", text)
        if numeric:
            found.add(f"{numeric[2]}-{int(numeric[1]):02d}")
        for name, number in names.items():
            for match in re.finditer(r"(?<!\w)" + name + r"\s+(20\d{2})(?!\d)", text):
                found.add(f"{match[1]}-{number:02d}")
    if len(found) != 1:
        raise RuntimeError("Could not identify the displayed calendar month")
    return found.pop()


def next_arrow(html):
    """Follow the portal's green next arrow, preserving its session URL."""
    page = BeautifulSoup(html, "html.parser")
    for image in page.select("a[href] img"):
        hint = " ".join(str(image.get(key, "")) for key in ("src", "alt", "title")).lower()
        if "go-next" not in hint and "next month" not in hint:
            continue
        url = urljoin(config.HOST.rstrip("/") + "/", image.find_parent("a")["href"])
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if (parsed.scheme != "https" or parsed.netloc != "service2.diplo.de" or
                parsed.path.split(";")[0] != "/rktermin/extern/appointment_showMonth.do" or
                any(query.get(key) != [value] for key, value in
                    (("locationCode", "niko"), ("realmId", "926"), ("categoryId", "1860")))):
            raise RuntimeError("Next arrow points outside the configured appointment category")
        return url
    return None


def check_months(handler, result, response_path=Path("target/response.html")):
    """Check up to three months with at most two forward-arrow requests."""
    html = response_path.read_text(encoding="utf-8")
    result.update(months=[], navigation=[], dates=[])
    current = displayed_month(html)
    for index in range(3):
        dates = available_dates(html)
        result["months"].append({"month": current, "checked": True, "dates": dates})
        result["dates"] = sorted(set(result["dates"] + dates), key=lambda d: datetime.strptime(d, "%d.%m.%Y"))
        if index == 2:
            break
        year, month = map(int, current.split("-"))
        expected = f"{year + (month == 12):04d}-{month % 12 + 1:02d}"
        arrow = next_arrow(html)
        if not arrow:
            result["navigation"].append({"from": current, "requested": expected, "displayed": current, "status": "no_arrow"})
            result["navigation_note"] = f"No next-month arrow after {current}; {expected} was not checked."
            break
        if not handler._curl(arrow, str(response_path)):
            raise RuntimeError("Next-month arrow request failed")
        html = response_path.read_text(encoding="utf-8")
        observed = displayed_month(html)
        available_dates(html)  # A CAPTCHA or error page is never a normal stop.
        result["navigation"].append({"from": current, "requested": expected, "displayed": observed,
                                     "status": "stayed" if observed == current else "advanced"})
        if observed == current:
            result["navigation_note"] = f"Tried {expected} once; the portal stayed on {current}. {expected} was not checked."
            break
        if observed != expected:
            raise RuntimeError("Next arrow displayed an unexpected calendar month")
        current = observed
    return result["dates"]


def main():
    result = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "target": "niko:926:1860", "auto_book": False,
              "coverage": "current month plus up to two next-arrow moves"}
    exit_code = 0
    try:
        for name in ("CAPTCHA_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            if not getattr(config, name):
                raise RuntimeError(f"Missing GitHub Actions secret: {name}")
        # This entry point never calls the booking workflow or a booking method.
        config.AUTO_BOOK = False
        config.BOOKING_DRY_RUN = True
        handler = AppointmentHandler(str(Path.cwd()))
        if not handler.fetch_month_view():
            raise RuntimeError("Could not pass the portal CAPTCHA; availability is unknown")
        dates = check_months(handler, result)
        result.update(status="ok", dates=dates)
        notify_available(dates)
    except Exception as error:
        # Exception text from upstream could contain sensitive request data.
        # Only our explicit operational messages are included in the result.
        message = str(error) if isinstance(error, RuntimeError) else "Unexpected check failure"
        result.update(status="failed", error=message)
        exit_code = 1
    Path("result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("### Nicosia appointment check\n```json\n" +
                          json.dumps(result, indent=2) + "\n```\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

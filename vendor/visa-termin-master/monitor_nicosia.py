"""Notification-only cloud entry point using the upstream CAPTCHA workflow."""
import json
import calendar
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from lib import config, extractors
from lib.appointment_handler import AppointmentHandler
from lib.captcha_solver import FundsExhausted
from email_alerts import send_email
from response_snapshots import capture

PORTAL_URL = ("https://service2.diplo.de/rktermin/extern/appointment_showMonth.do"
              "?locationCode=niko&realmId=926&categoryId=1860")
MAX_ARROW_REQUESTS = 24


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
    notify(text)


def notify(text, subject=None):
    failed = []
    email = lambda body: send_email(body, subject=subject) if subject else send_email(body)
    for name, send in (("Telegram", telegram), ("email", email)):
        try:
            send(text)
        except RuntimeError:
            failed.append(name)
    if failed:
        raise RuntimeError("Alert delivery failed for: " + ", ".join(failed))


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


def calendar_arrow(html, direction):
    """Read a portal arrow, preserving and validating its session URL."""
    page = BeautifulSoup(html, "html.parser")
    for image in page.select("a[href] img"):
        hint = " ".join(str(image.get(key, "")) for key in ("src", "alt", "title")).lower()
        names = ("go-next", "next month") if direction == "next" else ("go-previous", "previous month")
        if not any(name in hint for name in names):
            continue
        url = urljoin(config.HOST.rstrip("/") + "/", image.find_parent("a")["href"])
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if (parsed.scheme != "https" or parsed.netloc != "service2.diplo.de" or
                parsed.path.split(";")[0] != "/rktermin/extern/appointment_showMonth.do" or
                any(query.get(key) != [value] for key, value in
                    (("locationCode", "niko"), ("realmId", "926"), ("categoryId", "1860")))):
            raise RuntimeError("Calendar arrow points outside the configured appointment category")
        return url
    return None


def next_arrow(html):
    return calendar_arrow(html, "next")


def adjacent_month(current, step):
    year, month = map(int, current.split("-"))
    year, month = divmod(year * 12 + month - 1 + step, 12)
    return f"{year:04d}-{month + 1:02d}"


def current_month():
    return datetime.now(ZoneInfo("Asia/Famagusta")).strftime("%Y-%m")


def check_months(handler, result, response_path=Path("target/response.html")):
    """Reach this month's calendar, then check forward until an arrow stops."""
    target = current_month()  # Keep one local month for the entire scan.
    html = response_path.read_text(encoding="utf-8")
    capture(html, result, "After CAPTCHA", directory=response_path.parent / "snapshots")
    result.update(start_month=target, months=[], navigation=[], dates=[])
    anchored, notes = False, []
    for moves in range(MAX_ARROW_REQUESTS + 1):
        current = displayed_month(html)
        dates = available_dates(html)
        if not anchored and current == target:
            anchored = True
            if moves:
                notes.append(f"Reached current month {target}.")
        if anchored:
            result["months"].append({"month": current, "checked": True, "dates": dates})
            result["dates"] = sorted(set(result["dates"] + dates), key=lambda d: datetime.strptime(d, "%d.%m.%Y"))
        direction = "back" if not anchored and current > target else "next"
        expected = adjacent_month(current, -1 if direction == "back" else 1)
        if moves == MAX_ARROW_REQUESTS:
            if not anchored:
                raise RuntimeError(f"Could not reach current month {target} within the arrow limit")
            notes.append(f"Stopped at the {MAX_ARROW_REQUESTS}-request safety limit; {expected} was not checked.")
            break
        arrow = calendar_arrow(html, "previous" if direction == "back" else "next")
        if not arrow:
            result["navigation"].append({"direction": direction, "from": current, "requested": expected,
                                         "displayed": current, "status": "no_arrow"})
            if not anchored:
                raise RuntimeError(f"Could not reach current month {target}; no {direction} arrow after {current}")
            notes.append(f"No next-month arrow after {current}; {expected} was not checked.")
            break
        if not handler._curl(arrow, str(response_path)):
            raise RuntimeError("Calendar-arrow request failed")
        html = response_path.read_text(encoding="utf-8")
        capture(html, result, f"After {direction} arrow", requested=expected,
                directory=response_path.parent / "snapshots")
        observed = displayed_month(html)
        available_dates(html)  # A CAPTCHA or error page is never a normal stop.
        if observed not in (current, expected):
            raise RuntimeError("Calendar arrow displayed an unexpected calendar month")
        result["navigation"].append({"direction": direction, "from": current, "requested": expected,
                                     "displayed": observed, "status": "stayed" if observed == current else "advanced"})
        if observed == current:
            if not anchored:
                raise RuntimeError(f"Could not reach current month {target}; the portal stayed on {current}")
            notes.append(f"Tried {expected} once; the portal stayed on {current}. {expected} was not checked.")
            break
    result["navigation_note"] = " ".join(notes)
    return result["dates"]


def main():
    result = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "target": "niko:926:1860", "auto_book": False,
              "coverage": "current local month onward until blocked, with a 24-arrow safety limit"}
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
        result["captcha_funds_status"] = "usable"
        dates = check_months(handler, result)
        result.update(status="ok", dates=dates)
        notify_available(dates)
    except FundsExhausted:
        result.update(status="failed", captcha_funds_status="exhausted",
                      error="2Captcha funds exhausted — top up required")
        exit_code = 1
        try:
            notify("2Captcha funds exhausted — North Nicosia visa monitor\n"
                   "2Captcha reported ERROR_ZERO_BALANCE. Top up your 2Captcha account.\n"
                   "Appointments could not be checked. Automatic checks will keep trying on schedule.",
                   subject="ACTION REQUIRED - 2Captcha funds exhausted")
        except RuntimeError as error:
            result["notification_error"] = str(error)
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

import sys
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor_nicosia import available_dates, telegram


def test_known_empty_page():
    assert available_dates('<p>Unfortunately, there are no appointments available at this time.</p>') == []


@pytest.mark.parametrize("html", ["<html>Maintenance</html>", '<input name="captchaText">'])
def test_unknown_page_is_not_no_appointments(html):
    with pytest.raises(RuntimeError):
        available_dates(html)


def test_only_bookable_links_are_dates():
    assert available_dates('<a href="extern/appointment_showDay.do?locationCode=niko&amp;realmId=926&amp;categoryId=1860&amp;dateStr=15.12.2099">Book</a>') == ["15.12.2099"]


def test_telegram_api_rejection_is_a_failure():
    with patch("monitor_nicosia.requests.post", return_value=Mock(status_code=200, json=lambda: {"ok": False})):
        with pytest.raises(RuntimeError):
            telegram("test")


@pytest.mark.parametrize("failed", [None, "telegram", "send_email"])
def test_exhausted_funds_stops_retries_saves_status_and_attempts_both_alerts(tmp_path, monkeypatch, failed):
    import json
    import monitor_nicosia
    from lib import config
    monkeypatch.chdir(tmp_path)
    for name in ("CAPTCHA_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.setattr(config, name, "test-value")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "captcha.jpg").write_bytes(b"fake image")
    response = Mock()
    response.json.return_value = {"status": 0, "request": "ERROR_ZERO_BALANCE"}
    with patch("lib.appointment_handler.AppointmentHandler.fetch_captcha_page", return_value=True) as fetch, \
         patch("lib.appointment_handler.extractors.extract_captcha_image", return_value=True), \
         patch("requests.post", return_value=response) as submit, \
         patch("monitor_nicosia.check_months") as scan, \
         patch("monitor_nicosia.telegram") as chat, patch("monitor_nicosia.send_email") as email:
        if failed:
            (chat if failed == "telegram" else email).side_effect = RuntimeError("Delivery failed")
        assert monitor_nicosia.main() == 1
        fetch.assert_called_once()
        submit.assert_called_once()
        scan.assert_not_called()
        chat.assert_called_once()
        email.assert_called_once()
        assert "ERROR_ZERO_BALANCE" in chat.call_args.args[0]
        assert email.call_args.kwargs["subject"] == "ACTION REQUIRED - 2Captcha funds exhausted"
    result = json.loads((tmp_path / "result.json").read_text())
    assert result["status"] == "failed"
    assert result["captcha_funds_status"] == "exhausted"
    assert result["error"] == "2Captcha funds exhausted — top up required"
    assert bool(result.get("notification_error")) == bool(failed)


def test_portal_failure_does_not_claim_funds_exhausted_or_send_alert(tmp_path, monkeypatch):
    import json
    import monitor_nicosia
    from lib import config
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", "")
    for name in ("CAPTCHA_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        monkeypatch.setattr(config, name, "test-value")
    with patch("monitor_nicosia.AppointmentHandler.fetch_month_view", return_value=False), \
         patch("monitor_nicosia.telegram") as chat, patch("monitor_nicosia.send_email") as email:
        assert monitor_nicosia.main() == 1
        chat.assert_not_called()
        email.assert_not_called()
    result = json.loads((tmp_path / "result.json").read_text())
    assert "captcha_funds_status" not in result

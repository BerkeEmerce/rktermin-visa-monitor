import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from email_alerts import send_email
from monitor_nicosia import notify_available


@pytest.mark.parametrize("recipients", ["berkeemerce2002@gmail.com", "berkeemerce2002@gmail.com, emerce75@gmail.com"])
def test_smtp_sends_to_requested_recipient(monkeypatch, recipients):
    for key, value in {"SMTP_HOST": "smtp.example.com", "SMTP_USERNAME": "sender", "SMTP_PASSWORD": "secret",
                       "EMAIL_FROM": "sender@example.com", "EMAIL_TO": recipients, "SMTP_PORT": "465"}.items():
        monkeypatch.setenv(key, value)
    with patch("email_alerts.smtplib.SMTP_SSL") as connection:
        smtp = connection.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        send_email("Available on 03.01.2027")
        from email.utils import getaddresses
        message = smtp.send_message.call_args.args[0]
        assert [address for _, address in getaddresses(message.get_all("To"))] == recipients.split(", ")


@pytest.mark.parametrize("failed", ["telegram", "send_email", None])
def test_channels_are_attempted_independently(failed):
    with patch("monitor_nicosia.telegram") as telegram, patch("monitor_nicosia.send_email") as email:
        if failed:
            (telegram if failed == "telegram" else email).side_effect = RuntimeError("Delivery failed")
            with pytest.raises(RuntimeError):
                notify_available(["03.01.2027"])
        else:
            notify_available(["03.01.2027"])
        telegram.assert_called_once()
        email.assert_called_once()


def test_no_alerts_for_empty_check():
    with patch("monitor_nicosia.telegram") as telegram, patch("monitor_nicosia.send_email") as email:
        notify_available([])
        telegram.assert_not_called()
        email.assert_not_called()

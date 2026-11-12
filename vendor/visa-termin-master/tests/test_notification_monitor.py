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

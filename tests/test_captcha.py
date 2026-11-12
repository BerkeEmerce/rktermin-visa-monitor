import io
from dataclasses import replace
from datetime import date
from unittest.mock import Mock,patch
import pytest
from visa_monitor.captcha import LocalOCR,extract_challenge,image_bytes
from visa_monitor.models import CheckError,Status
from visa_monitor.portal_client import PortalClient
from test_calendar import FakeTransport

MONTH = date(2026,11,1)
TODAY = date(2026,11,12)

def test_extract_session_and_dispatch(fixture,config):
    challenge = extract_challenge(fixture("captcha.html"),config.month_url(MONTH))
    assert challenge.action.endswith(";jsessionid=fixture")
    assert ("action:appointment_showMonth","Continue") in challenge.fields
    assert image_bytes(challenge,"",None)==b"sample1"

def test_css_embedded_image(fixture,config):
    html = fixture("captcha.html").replace('<img src="data:image/png;base64,c2FtcGxlMQ==">',"<captcha><div style=\"background:url('data:image/png;base64,c2FtcGxlMQ==')\"></div></captcha>")
    assert extract_challenge(html,config.month_url(MONTH)).image.startswith("data:image/png")

def test_default_no_submission(fixture,config):
    transport = FakeTransport([fixture("captcha.html")])
    with pytest.raises(CheckError) as caught:
        PortalClient(config,transport).open_calendar(MONTH,TODAY)
    assert caught.value.status==Status.CAPTCHA_FAILED
    assert len(transport.calls)==1

def test_rejection_retry_limit(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    first = fixture("captcha.html")
    second = first.replace("c2FtcGxlMQ==","c2FtcGxlMg==")
    transport = FakeTransport([first,second,first])
    client = PortalClient(config,transport,Mock(recognize=Mock(return_value="abc123")))
    with pytest.raises(CheckError,match="retry limit"):
        client.open_calendar(MONTH,TODAY)
    assert client.metrics["submitted"]==2 and client.metrics["rejected"]==2
    assert len(transport.calls)==3

def test_acceptance_needs_parsed_calendar(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    client = PortalClient(config,FakeTransport([fixture("captcha.html"),fixture("nov_empty.html")]),Mock(recognize=Mock(return_value="abc123")))
    client.open_calendar(MONTH,TODAY)
    assert client.metrics["accepted"]==1

def test_captcha_disappearing_is_not_acceptance(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    client = PortalClient(config,FakeTransport([fixture("captcha.html"),"<p>Try later</p>"]),Mock(recognize=Mock(return_value="abc123")))
    with pytest.raises(CheckError):
        client.open_calendar(MONTH,TODAY)
    assert client.metrics["accepted"]==0

def test_no_repeated_same_challenge(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    html = fixture("captcha.html")
    client = PortalClient(config,FakeTransport([html,html]),Mock(recognize=Mock(return_value="abc123")))
    with pytest.raises(CheckError,match="Repeated CAPTCHA"):
        client.open_calendar(MONTH,TODAY)
    assert client.metrics["submitted"]==1

def test_never_submit_booking_form(fixture,config):
    html = fixture("captcha.html").replace("appointment_showMonth.do;","appointment_showForm.do;")
    with pytest.raises(CheckError,match="non-calendar"):
        extract_challenge(html,config.month_url(MONTH))

def test_invalid_image(fixture,config):
    challenge = extract_challenge(fixture("captcha.html").replace("c2FtcGxlMQ==","!invalid!"),config.month_url(MONTH))
    with pytest.raises(CheckError):
        image_bytes(challenge,"",None)

def test_local_preprocessing_votes():
    pytest.importorskip("cv2")
    from PIL import Image
    data = io.BytesIO()
    Image.new("RGB",(120,40),"white").save(data,format="PNG")
    with patch("pytesseract.image_to_string",return_value="abc123") as recognize:
        assert LocalOCR().recognize(data.getvalue())=="abc123"
    assert recognize.call_count==8
    # This tests the pipeline only, not real CAPTCHA recognition accuracy.

def test_ocr_failure_is_safe():
    assert LocalOCR().recognize(b"not an image") is None


def test_hidden_dispatch_refused(fixture,config):
    html = fixture("captcha.html").replace('<input name="captchaText"', '<input type="hidden" name="action:appointment_addAppointment"><input name="captchaText"')
    with pytest.raises(CheckError,match="hidden dispatch"):
        extract_challenge(html,config.month_url(MONTH))

def test_duplicate_category_refused(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    html = fixture("captcha.html").replace('<input name="captchaText"', '<input type="hidden" name="categoryId" value="999"><input name="captchaText"')
    client = PortalClient(config,FakeTransport([html]))
    with pytest.raises(CheckError,match="category mismatch"):
        client.open_calendar(MONTH,TODAY)


def test_unreadable_image_refreshes_through_normal_form(fixture,config):
    config = replace(config,captcha_mode="ocr",ocr_permitted=True)
    first = fixture("captcha.html").replace('</form>', '<input type="submit" name="action:appointment_refreshCaptchamonth" value="New image"></form>')
    second = first.replace("c2FtcGxlMQ==","c2FtcGxlMg==").replace("appointment_showMonth.do;", "appointment_refreshCaptchamonth.do;")
    transport = FakeTransport([first,second,fixture("nov_empty.html")])
    client = PortalClient(config,transport,Mock(recognize=Mock(side_effect=[None,"abc123"])))
    client.open_calendar(MONTH,TODAY)
    assert client.metrics["images"] == 2
    assert client.metrics["refreshed"] == 1
    assert client.metrics["submitted"] == 1
    assert client.metrics["accepted"] == 1
    refresh_fields = transport.calls[1][2]
    assert ("action:appointment_refreshCaptchamonth", "New image") in refresh_fields
    assert not any(name == "action:appointment_showMonth" for name,value in refresh_fields)
    assert "appointment_refreshCaptchamonth.do;" in transport.calls[2][1]

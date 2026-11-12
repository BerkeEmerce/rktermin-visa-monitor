from dataclasses import replace
from datetime import datetime,timezone
from unittest.mock import Mock
import pytest
import requests
import responses
from visa_monitor.config import Config
from visa_monitor.models import CheckError,Status
from visa_monitor.portal_client import Transport,retry_after_seconds

URL = "https://service2.diplo.de/rktermin/extern/appointment_showMonth.do"

def transport(config):
    return Transport(config,sleep=Mock())

@responses.activate
@pytest.mark.parametrize("status",[401,403,429])
def test_access_denied_does_not_retry(status,config):
    responses.get(URL,status=status,headers={"Retry-After":"172800"})
    with pytest.raises(CheckError) as caught:
        transport(config).request("GET",URL)
    assert caught.value.status==Status.ACCESS_BLOCKED
    assert caught.value.retry_after==172800
    assert len(responses.calls)==1

@responses.activate
def test_get_network_retry_bound(config):
    responses.get(URL,body=requests.Timeout("private URL must not leak"))
    with pytest.raises(CheckError) as caught:
        transport(config).request("GET",URL)
    assert caught.value.status==Status.NETWORK_ERROR
    assert "private" not in str(caught.value)
    assert len(responses.calls)==3

@responses.activate
def test_post_not_replayed_after_timeout(config):
    responses.post(URL,body=requests.Timeout())
    with pytest.raises(CheckError):
        transport(config).request("POST",URL,[("captchaText","fixture")])
    assert len(responses.calls)==1

@responses.activate
def test_transient_server_recovers(config):
    responses.get(URL,status=503)
    responses.get(URL,body="ok")
    assert transport(config).request("GET",URL).text=="ok"
    assert len(responses.calls)==2

@responses.activate
def test_server_retry_after_is_respected(config):
    responses.get(URL,status=503,headers={"Retry-After":"3600"})
    with pytest.raises(CheckError) as caught:
        transport(config).request("GET",URL)
    assert caught.value.retry_after==3600 and len(responses.calls)==1

@responses.activate
def test_robots_disallow(config):
    responses.get("https://service2.diplo.de/robots.txt",body="User-agent: *\nDisallow: /rktermin/")
    t = transport(config)
    t.check_robots()
    with pytest.raises(CheckError) as caught:
        t.request("GET",URL)
    assert caught.value.status==Status.ACCESS_BLOCKED and len(responses.calls)==1

@responses.activate
def test_robots_404_allows(config):
    responses.get("https://service2.diplo.de/robots.txt",status=404)
    responses.get(URL,body="ok")
    t = transport(config)
    t.check_robots()
    assert t.request("GET",URL).text=="ok"

@responses.activate
def test_robots_delay(config):
    responses.get("https://service2.diplo.de/robots.txt",body="User-agent: *\nDisallow:\nCrawl-delay: 30")
    responses.get(URL,body="ok")
    t = transport(config)
    t.check_robots()
    t.request("GET",URL)
    assert t.sleep.call_args[0][0]>29

@responses.activate
def test_redirect_keeps_cookie_session(config):
    target = URL+"?verified=1"
    responses.get(URL,status=302,headers={"Location":target,"Set-Cookie":"JSESSIONID=fixture; Path=/"})
    responses.get(target,body="ok")
    t = transport(config)
    assert t.page("GET",URL)[0]=="ok"
    assert "JSESSIONID=fixture" in responses.calls[1].request.headers["Cookie"]

@responses.activate
def test_cross_origin_redirect_blocked(config):
    responses.get(URL,status=302,headers={"Location":"https://evil.invalid/"})
    with pytest.raises(CheckError):
        transport(config).page("GET",URL)
    assert len(responses.calls)==1

@responses.activate
def test_redirect_limit(config):
    responses.get(URL,status=302,headers={"Location":URL})
    with pytest.raises(CheckError,match="Too many redirects"):
        transport(config).page("GET",URL)
    assert len(responses.calls)==4

def test_no_booking_post(config):
    with pytest.raises(CheckError,match="Refusing booking"):
        transport(config).request("POST",URL.replace("showMonth","addAppointment"))

def test_retry_after_http_date():
    now = datetime(2026,11,12,12,tzinfo=timezone.utc)
    assert retry_after_seconds("Thu, 12 Nov 2026 13:00:00 GMT",now)==3600
    assert retry_after_seconds("invalid",now)==0

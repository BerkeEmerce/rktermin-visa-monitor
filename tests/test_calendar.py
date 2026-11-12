from dataclasses import replace
from datetime import date
import pytest
from visa_monitor.availability import add_months,check_availability
from visa_monitor.calendar_parser import parse_calendar,portal_url
from visa_monitor.models import CheckError,Status
from visa_monitor.portal_client import PortalClient

NOV = date(2026,11,1)
TODAY = date(2026,11,12)

def parse(html,config,month=NOV):
    return parse_calendar(html,config.month_url(month),month,TODAY,config)

def test_no_availability_message(fixture,config):
    assert parse(fixture("nov_empty.html"),config).dates==[]


def test_same_month_navigation_with_different_day_anchors(fixture,config):
    from bs4 import BeautifulSoup
    doc = BeautifulSoup(fixture("nov_empty.html"), "html.parser")
    link = next(a for a in doc.select("a[href]") if "01.12.2026" in a["href"])
    duplicate = doc.new_tag("a", href=link["href"].replace("01.12.2026", "30.12.2026"))
    doc.append(duplicate)
    assert date(2026,12,1) in parse(str(doc),config).navigation
    duplicate["href"] += "&unexpected=1"
    with pytest.raises(CheckError,match="Ambiguous month"):
        parse(str(doc),config)

def test_actual_day_link_evidence(fixture,config):
    page = parse(fixture("nov_available.html"),config)
    assert page.dates==[date(2026,11,18),date(2026,11,21)]

def test_empty_calendar_without_message(fixture,config):
    assert parse(fixture("nov_grid.html"),config).dates==[]

@pytest.mark.parametrize("name",["unexpected.html","message_only.html","expired.html"])
def test_failed_pages_never_empty(name,fixture,config):
    with pytest.raises(CheckError):
        parse(fixture(name),config)

def test_displayed_month_required(fixture,config):
    with pytest.raises(CheckError,match="Displayed month"):
        parse(fixture("dec_empty.html"),config)

def test_category_mismatch(fixture,config):
    with pytest.raises(CheckError,match="different category"):
        parse(fixture("nov_available.html").replace("categoryId=1860","categoryId=999"),config)

def test_off_site_links(fixture,config):
    with pytest.raises(CheckError):
        parse(fixture("nov_available.html").replace("extern/appointment_showDay", "https://evil.invalid/appointment_showDay"),config)

def test_contradictory_page(fixture,config):
    from visa_monitor.calendar_parser import NO_APPOINTMENTS
    with pytest.raises(CheckError,match="Contradictory"):
        parse(fixture("nov_available.html")+NO_APPOINTMENTS,config)

def test_ignores_past_dates(fixture,config):
    html = fixture("nov_available.html").replace("18.11.2026","01.11.2026")
    assert parse(html,config).dates==[date(2026,11,21)]

def test_disabled_link(fixture,config):
    html = fixture("nov_available.html").replace('<a class="date"','<a aria-disabled="true" class="date"',1)
    assert parse(html,config).dates==[date(2026,11,21)]

def test_root_relative_resolution():
    assert portal_url("extern/appointment_showMonth.do", "https://service2.diplo.de/rktermin/extern/a.do")=="https://service2.diplo.de/rktermin/extern/appointment_showMonth.do"

@pytest.mark.parametrize("start,n,expected",[(date(2026,12,31),1,date(2027,1,1)),(date(2026,11,30),2,date(2027,1,1)),(date(2028,2,29),1,date(2028,3,1))])
def test_month_rollover(start,n,expected):
    assert add_months(start,n)==expected

class FakeTransport:
    def __init__(self,pages):
        self.pages = iter(pages)
        self.calls = []
    def check_robots(self):
        pass
    def page(self,method,url,data=None):
        self.calls.append((method,url,data))
        value = next(self.pages)
        if isinstance(value,Exception):
            raise value
        return value,url

def test_three_real_navigation_links(fixture,config):
    transport = FakeTransport([fixture("nov_empty.html"),fixture("dec_empty.html"),fixture("jan_empty.html")])
    result = check_availability(PortalClient(config,transport),TODAY)
    assert result.status==Status.UNAVAILABLE
    assert result.months==["2026-11","2026-12","2027-01"]
    assert ";jsessionid=fixture" in transport.calls[1][1]
    assert "01.01.2027" in transport.calls[2][1]
    assert all(method=="GET" for method,_,_ in transport.calls)

def test_partial_keeps_confirmed_dates(fixture,config):
    transport = FakeTransport([fixture("nov_available.html"),CheckError(Status.NETWORK_ERROR,"fixture timeout")])
    result = check_availability(PortalClient(config,transport),TODAY)
    assert result.status==Status.PARTIAL_CHECK
    assert not result.complete
    assert result.dates==["2026-11-18","2026-11-21"]
    assert result.error=="NETWORK_ERROR"

def test_expired_session_mid_navigation(fixture,config):
    transport = FakeTransport([fixture("nov_empty.html"),fixture("expired.html")])
    result = check_availability(PortalClient(config,transport),TODAY)
    assert result.status==Status.PARTIAL_CHECK and result.error=="CAPTCHA_FAILED"

def test_missing_navigation_fails(fixture,config):
    html = fixture("nov_empty.html").replace("appointment_showMonth.do","unknown.do")
    result = check_availability(PortalClient(config,FakeTransport([html])),TODAY)
    assert result.status==Status.PARTIAL_CHECK

def test_december_three_months(fixture,config):
    transport = FakeTransport([fixture("dec_empty.html"),fixture("jan_empty.html"),fixture("feb_empty.html")])
    result = check_availability(PortalClient(config,transport),date(2026,12,15))
    assert result.complete and result.months==["2026-12","2027-01","2027-02"]


def test_historical_upstream_numeric_month_fixture(fixture,config):
    page = parse_calendar(fixture("historical_calendar.html"),config.month_url(date(2019,12,1)),
                          date(2019,12,1),date(2019,12,1),config)
    assert page.dates==[date(2019,12,11),date(2019,12,12),date(2019,12,13)]

def test_legacy_empty_page_requires_month_and_navigation(fixture,config):
    from bs4 import BeautifulSoup
    doc = BeautifulSoup(fixture("nov_empty.html"),"html.parser")
    doc.select_one('table').decompose()
    html = '<div id="content">'+str(doc).replace("November 2026","11/2026")+'</div>'
    assert parse(html,config).dates==[]
    with pytest.raises(CheckError):
        parse(html.replace("appointment_showMonth.do","unknown.do"),config)


def test_new_calendar_button_cannot_be_misreported_empty(fixture,config):
    html = fixture("nov_grid.html").replace('<td>18</td>','<td><button>18</button></td>')
    with pytest.raises(CheckError,match="Unrecognized calendar controls"):
        parse(html,config)

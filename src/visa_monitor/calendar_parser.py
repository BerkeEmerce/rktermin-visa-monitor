import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import parse_qs, urljoin, urlsplit
from bs4 import BeautifulSoup
from .config import BASE
from .models import CheckError, Status

NO_APPOINTMENTS = ("Unfortunately, there are no appointments available at this time. "
                   "New appointments will be made available for booking at regular intervals.")
MONTH_NAMES = {n.lower():i for i,n in enumerate(calendar.month_name) if n}
MONTH_NAMES.update(dict(zip("januar februar märz april mai juni juli august september oktober november dezember".split(),range(1,13))))

def soup(html):
    return BeautifulSoup(html,"html.parser")

def has_captcha(html):
    return bool(soup(html).select('input[name="captchaText"],captcha,input[name*="captcha" i]'))

def portal_url(href,current):
    resolved = urljoin(BASE if href.startswith("extern/") else current,href)
    parsed = urlsplit(resolved)
    if parsed.scheme != "https" or parsed.netloc != "service2.diplo.de" or not parsed.path.startswith("/rktermin/"):
        raise CheckError(Status.PARSE_ERROR,"Unsafe or unexpected portal link")
    return resolved

def endpoint(url):
    return urlsplit(url).path.split(";")[0].rsplit("/",1)[-1]

def link_date(url):
    values = parse_qs(urlsplit(url).query).get("dateStr",[])
    if len(values)!=1:
        raise CheckError(Status.PARSE_ERROR,"Missing or ambiguous link date")
    try:
        return datetime.strptime(values[0],"%d.%m.%Y").date()
    except ValueError:
        raise CheckError(Status.PARSE_ERROR,"Invalid link date") from None

def verify_target(url,config):
    query = parse_qs(urlsplit(url).query)
    if any(query.get(k)!=[v] for k,v in config.params.items()):
        raise CheckError(Status.PARSE_ERROR,"Portal link targets a different category")

def month_heading(doc):
    found = set()
    for node in doc.select('h1,h2,h3,h4,caption,th,.calendar-title,.month-title'):
        text = " ".join(node.get_text(" ",strip=True).split()).lower()
        numeric = re.fullmatch(r"(0?[1-9]|1[0-2]) */ *(20[0-9]{2})",text)
        if numeric:
            found.add(date(int(numeric[2]),int(numeric[1]),1))
        for name,number in MONTH_NAMES.items():
            for match in re.finditer(r"(?<!\w)"+re.escape(name)+r"\s+(20\d{2})(?!\d)",text):
                found.add(date(int(match[1]),number,1))
    if len(found)!=1:
        raise CheckError(Status.PARSE_ERROR,"Displayed month/year missing or ambiguous")
    return found.pop()

@dataclass
class CalendarPage:
    month: date
    dates: list[date]
    navigation: dict[date,str]

def parse_calendar(html,url,expected,today,config):
    if has_captcha(html):
        raise CheckError(Status.CAPTCHA_FAILED,"CAPTCHA required or session expired")
    doc = soup(html)
    text = " ".join(doc.get_text(" ",strip=True).split())
    if any(x in text.lower() for x in ("access denied","too many requests","zugriff verweigert")):
        raise CheckError(Status.ACCESS_BLOCKED,"Portal denied access")
    displayed = month_heading(doc)
    if displayed!=expected:
        raise CheckError(Status.PARSE_ERROR,"Displayed month differs from requested month")
    dates,navigation = set(),{}
    for a in doc.select("a[href]"):
        href = a["href"]
        if "appointment_showDay.do" not in href and "appointment_showMonth.do" not in href:
            continue
        if a.get("aria-disabled")=="true" or "disabled" in a.get("class",[]):
            continue
        target = portal_url(href,url)
        verify_target(target,config)
        day = link_date(target)
        if endpoint(target)=="appointment_showMonth.do":
            month = day.replace(day=1)
            if month in navigation and navigation[month]!=target:
                raise CheckError(Status.PARSE_ERROR,"Ambiguous month navigation")
            navigation[month] = target
        elif endpoint(target)=="appointment_showDay.do":
            if day.replace(day=1)!=displayed:
                raise CheckError(Status.PARSE_ERROR,"Day link outside displayed month")
            if day>=today:
                dates.add(day)
    empty_message = NO_APPOINTMENTS.lower() in text.lower()
    if empty_message and dates:
        raise CheckError(Status.PARSE_ERROR,"Contradictory availability evidence")
    table = doc.select_one('table.calendar,table#calendar,table.appointment-calendar')
    index = displayed.year*12+displayed.month
    adjacent_nav = any(abs((m.year*12+m.month)-index)==1 for m in navigation)
    legacy_empty = empty_message and adjacent_nav and doc.select_one("#content") is not None
    if not dates and table is None and not legacy_empty:
        raise CheckError(Status.PARSE_ERROR,"No recognized calendar structure")
    if not dates and table is not None:
        for control in table.select('a[href],button,input,select,form,[onclick],[role="button"]'):
            if control.name!="a" or "onclick" in control.attrs:
                raise CheckError(Status.PARSE_ERROR,"Unrecognized calendar controls")
            target = portal_url(control.get("href",""),url)
            if endpoint(target) not in ("appointment_showMonth.do","appointment_showDay.do"):
                raise CheckError(Status.PARSE_ERROR,"Unrecognized calendar link")
    if not dates and not empty_message:
        days = {int(c.get_text(strip=True)) for c in table.select("td")
                if c.get_text(strip=True).isdigit() and 1<=int(c.get_text(strip=True))<=31}
        if days!=set(range(1,calendar.monthrange(displayed.year,displayed.month)[1]+1)):
            raise CheckError(Status.PARSE_ERROR,"Incomplete empty calendar evidence")
    return CalendarPage(displayed,sorted(dates),navigation)

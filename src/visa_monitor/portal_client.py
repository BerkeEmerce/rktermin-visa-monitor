import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests
from .calendar_parser import endpoint, has_captcha, parse_calendar, portal_url, verify_target
from .captcha import LocalOCR, extract_challenge, fingerprint, image_bytes
from .models import CheckError, Status

USER_AGENT = "RKTerminPersonalMonitor/0.1 (availability only; no booking)"

class Transport:
    def __init__(self,config,session=None,sleep=time.sleep):
        self.config = config
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"en"})
        self.sleep = sleep
        self.last_request = None
        self.robots = None
        self.robots_delay = 0

    def _wait(self):
        if self.last_request is not None:
            delay = max(self.config.delay,self.robots_delay)
            self.sleep(max(0,delay-(time.monotonic()-self.last_request)))
        self.last_request = time.monotonic()

    def request(self,method,url,data=None,robots_request=False):
        parsed = urlsplit(url)
        if parsed.scheme!="https" or parsed.netloc!="service2.diplo.de":
            raise CheckError(Status.PARSE_ERROR,"Refusing off-site request")
        if method=="POST" and endpoint(url) not in ("appointment_showMonth.do","appointment_captcha.do"):
            raise CheckError(Status.PARSE_ERROR,"Refusing booking or unexpected POST")
        if not robots_request and self.robots and not self.robots.can_fetch(USER_AGENT,url):
            raise CheckError(Status.ACCESS_BLOCKED,"robots.txt disallows requested URL")
        attempts = 1+(self.config.retries if method=="GET" else 0)
        for attempt in range(attempts):
            self._wait()
            try:
                response = self.session.request(method,url,data=data,timeout=self.config.timeout,allow_redirects=False)
            except requests.RequestException:
                if attempt+1==attempts:
                    raise CheckError(Status.NETWORK_ERROR,"HTTP transport failed") from None
                self.sleep(2**(attempt+1))
                continue
            if response.status_code in (401,403,429):
                retry = retry_after_seconds(response.headers.get("Retry-After",""))
                raise CheckError(Status.ACCESS_BLOCKED,f"Portal returned HTTP {response.status_code}",retry)
            if response.status_code in (500,502,503,504):
                retry = retry_after_seconds(response.headers.get("Retry-After",""))
                if retry:
                    raise CheckError(Status.NETWORK_ERROR,"Portal requested retry later",retry)
                if attempt+1==attempts:
                    raise CheckError(Status.NETWORK_ERROR,"Portal server temporarily unavailable")
                self.sleep(2**(attempt+1))
                continue
            if robots_request and response.status_code==404:
                return response
            if response.is_redirect and not robots_request:
                return response
            if response.status_code!=200:
                raise CheckError(Status.PARSE_ERROR,"Unexpected HTTP response")
            if len(response.content)>3_000_000:
                raise CheckError(Status.PARSE_ERROR,"Unexpectedly large portal response")
            return response
        raise AssertionError("Unreachable")

    def page(self,method,url,data=None):
        for _ in range(4):
            response = self.request(method,url,data=data)
            if not response.is_redirect:
                return response.text,response.url or url
            target = portal_url(response.headers.get("Location",""),url)
            if endpoint(target) not in ("appointment_showMonth.do","appointment_captcha.do"):
                raise CheckError(Status.PARSE_ERROR,"Unexpected portal redirect; adapter review required")
            if response.status_code in (301,302,303):
                method,data = "GET",None
            url = target
        raise CheckError(Status.PARSE_ERROR,"Too many redirects")

    def check_robots(self):
        response = self.request("GET","https://service2.diplo.de/robots.txt",robots_request=True)
        parser = RobotFileParser()
        parser.parse(response.text.splitlines() if response.status_code==200 else [])
        self.robots = parser
        self.robots_delay = parser.crawl_delay(USER_AGENT) or 0
        rate = parser.request_rate(USER_AGENT)
        if rate:
            self.robots_delay = max(self.robots_delay,rate.seconds/rate.requests)

def retry_after_seconds(value,now=None):
    try:
        return max(0,int(value))
    except (ValueError,TypeError):
        try:
            return max(0,(parsedate_to_datetime(value)-(now or datetime.now(timezone.utc))).total_seconds())
        except (ValueError,TypeError,OverflowError):
            return 0

class PortalClient:
    def __init__(self,config,transport=None,ocr=None):
        self.config = config
        self.transport = transport or Transport(config)
        self.ocr = ocr or LocalOCR()
        self.metrics = {"images":0,"recognized":0,"submitted":0,"accepted":0,"rejected":0}

    def open_calendar(self,month,today):
        self.transport.check_robots()
        html,url = self.transport.page("GET",self.config.month_url(month))
        seen = set()
        for _ in range(self.config.captcha_attempts):
            if not has_captcha(html):
                parse_calendar(html,url,month,today,self.config)
                return html,url
            if self.config.captcha_mode!="ocr" or not self.config.ocr_permitted:
                raise CheckError(Status.CAPTCHA_FAILED,"Unattended OCR disabled; permission and live validation pending")
            challenge = extract_challenge(html,url)
            hidden = dict(challenge.fields)
            if any([v for k,v in challenge.fields if k==name] not in ([],[expected])
                   for name,expected in self.config.params.items()):
                raise CheckError(Status.PARSE_ERROR,"CAPTCHA form category mismatch")
            content = image_bytes(challenge,url,self.transport)
            digest = fingerprint(content)
            if digest in seen:
                raise CheckError(Status.CAPTCHA_FAILED,"Repeated CAPTCHA challenge; stopping")
            seen.add(digest)
            self.metrics["images"] += 1
            value = self.ocr.recognize(content)
            if not value:
                raise CheckError(Status.CAPTCHA_FAILED,"Local OCR produced no reliable candidate")
            self.metrics["recognized"] += 1
            fields = [(k,v) for k,v in challenge.fields if k!="captchaText"]
            for k,v in self.config.params.items():
                if k not in hidden:
                    fields.append((k,v))
            fields.append(("captchaText",value))
            self.metrics["submitted"] += 1
            html,url = self.transport.page("POST",challenge.action,fields)
            if has_captcha(html):
                self.metrics["rejected"] += 1
            else:
                parse_calendar(html,url,month,today,self.config)
                self.metrics["accepted"] += 1
                return html,url
        raise CheckError(Status.CAPTCHA_FAILED,"CAPTCHA retry limit reached")

    def next_month(self,page,month,today):
        target = page.navigation.get(month)
        if target is None:
            raise CheckError(Status.PARSE_ERROR,"Next month navigation is missing")
        verify_target(target,self.config)
        html,url = self.transport.page("GET",target)
        return parse_calendar(html,url,month,today,self.config)

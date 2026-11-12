import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

BASE = "https://service2.diplo.de/rktermin/"

def boolean(env, name, default=False):
    value = env.get(name, str(default)).lower()
    if value not in ("true", "false"):
        raise ValueError(f"{name} must be true or false")
    return value == "true"

@dataclass(frozen=True)
class Config:
    location: str = "niko"
    realm: str = "926"
    category: str = "1860"
    location_name: str = "North Nicosia"
    timezone: str = "Asia/Nicosia"
    months: int = 3
    interval: int = 15
    captcha_attempts: int = 2
    timeout: int = 20
    delay: float = 3
    retries: int = 2
    dry_run: bool = True
    captcha_mode: str = "disabled"
    ocr_engine: str = "tesseract"
    captcha_length: int = 6
    ocr_permitted: bool = False
    failure_threshold: int = 3
    stale_hours: int = 6
    alert_hours: int = 24
    cooldown_hours: int = 24
    daily_summary: bool = True
    token: str = field(default="", repr=False)
    chat_id: str = field(default="", repr=False)

    def __post_init__(self):
        ZoneInfo(self.timezone)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,30}",self.location):
            raise ValueError("Invalid location code")
        if not self.realm.isdigit() or not self.category.isdigit():
            raise ValueError("Realm and category must be numeric")
        if not 1 <= self.months <= 3:
            raise ValueError("MONTHS_TO_CHECK must be between 1 and 3")
        if self.interval < 15 or self.interval % 15:
            raise ValueError("CHECK_INTERVAL_MINUTES must be a multiple of 15")
        if not 1 <= self.captcha_attempts <= 2:
            raise ValueError("MAX_CAPTCHA_ATTEMPTS must be 1 or 2")
        if not 1 <= self.timeout <= 30 or not 3 <= self.delay <= 30 or not 0 <= self.retries <= 2:
            raise ValueError("Request bounds: timeout 1..30, delay 3..30, retries 0..2")
        if min(self.failure_threshold,self.stale_hours,self.alert_hours,self.cooldown_hours)<1:
            raise ValueError("Health thresholds must be positive")
        if self.captcha_mode not in ("disabled","ocr"):
            raise ValueError("CAPTCHA_MODE must be disabled or ocr")
        if self.ocr_engine not in ("tesseract", "neural"):
            raise ValueError("OCR_ENGINE must be tesseract or neural")
        if not 4 <= self.captcha_length <= 10:
            raise ValueError("CAPTCHA_EXPECTED_LENGTH must be between 4 and 10")

    @classmethod
    def from_env(cls,env=None):
        e = os.environ if env is None else env
        if boolean(e,"AUTO_BOOK"):
            raise ValueError("AUTO_BOOK=true is prohibited; this program cannot book")
        strings = {"location":"LOCATION_CODE","realm":"REALM_ID","category":"CATEGORY_ID",
                   "location_name":"LOCATION_NAME","timezone":"TIMEZONE","captcha_mode":"CAPTCHA_MODE",
                   "token":"TELEGRAM_BOT_TOKEN","chat_id":"TELEGRAM_CHAT_ID", "ocr_engine":"OCR_ENGINE"}
        ints = {"months":"MONTHS_TO_CHECK","interval":"CHECK_INTERVAL_MINUTES",
                "captcha_attempts":"MAX_CAPTCHA_ATTEMPTS","timeout":"REQUEST_TIMEOUT_SECONDS",
                "retries":"NETWORK_RETRIES","failure_threshold":"FAILURE_ALERT_THRESHOLD",
                "stale_hours":"STALE_AFTER_HOURS","alert_hours":"OPERATIONAL_ALERT_HOURS",
                "cooldown_hours":"ACCESS_COOLDOWN_HOURS", "captcha_length":"CAPTCHA_EXPECTED_LENGTH"}
        args = {k:e[v] for k,v in strings.items() if v in e}
        args.update({k:int(e[v]) for k,v in ints.items() if v in e})
        if "REQUEST_DELAY_SECONDS" in e:
            args["delay"] = float(e["REQUEST_DELAY_SECONDS"])
        args.update(dry_run=boolean(e,"DRY_RUN",True),ocr_permitted=boolean(e,"OCR_PERMISSION_CONFIRMED"),
                    daily_summary=boolean(e,"DAILY_SUMMARY",True))
        return cls(**args)

    @property
    def target(self):
        return f"{self.location}:{self.realm}:{self.category}:{self.timezone}:{self.months}"

    @property
    def params(self):
        return {"locationCode":self.location,"realmId":self.realm,"categoryId":self.category}

    def month_url(self,day):
        return BASE+"extern/appointment_showMonth.do?"+urlencode(self.params|{"dateStr":day.strftime("%d.%m.%Y")})

    @property
    def booking_url(self):
        return BASE+"extern/choose_category.do?"+urlencode(self.params)

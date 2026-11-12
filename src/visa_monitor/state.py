import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date, datetime, timedelta
from pathlib import Path

@dataclass
class State:
    version: int = 1
    target: str = ""
    first_run: str | None = None
    last_check: str | None = None
    last_success: str | None = None
    months: list[str] = field(default_factory=list)
    notified_dates: list[str] = field(default_factory=list)
    email_notified_dates: list[str] = field(default_factory=list)
    delivery_errors: dict = field(default_factory=dict)
    failures: int = 0
    last_error: str | None = None
    last_status: str | None = None
    last_notification: str | None = None
    last_operational_alert: str | None = None
    recovery_pending: bool = False
    day: str | None = None
    daily_successes: int = 0
    previous_day_successes: int = 0
    last_summary_day: str | None = None
    next_check: str | None = None
    blocked_until: str | None = None
    notification_error: bool = False
    captcha: dict = field(default_factory=dict)

    @classmethod
    def decode(cls,text):
        data = json.loads(text)
        if not isinstance(data,dict) or data.get("version")!=1:
            raise ValueError("Unsupported or invalid state; refusing to reset deduplication")
        if set(data)-{f.name for f in fields(cls)}:
            raise ValueError("Unknown state fields")
        state = cls(**data)
        for key in ("failures","daily_successes","previous_day_successes"):
            if not isinstance(getattr(state,key),int) or getattr(state,key)<0:
                raise ValueError("Invalid state counter")
        for key in ("first_run","last_check","last_success","next_check","blocked_until",
                    "last_notification","last_operational_alert"):
            value = getattr(state,key)
            if value is not None:
                if not isinstance(value,str) or datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError("State timestamps must have a timezone")
        if not isinstance(state.notified_dates,list):
            raise ValueError("Invalid notified dates")
        for value in state.notified_dates:
            if not isinstance(value,str):
                raise ValueError("Invalid notified date")
            date.fromisoformat(value)
        if not isinstance(state.email_notified_dates,list):
            raise ValueError("Invalid email notified dates")
        for value in state.email_notified_dates:
            if not isinstance(value,str):
                raise ValueError("Invalid email notified date")
            date.fromisoformat(value)
        if not isinstance(state.delivery_errors,dict):
            raise ValueError("Invalid delivery error state")
        return state

    def encode(self):
        return json.dumps(asdict(self),sort_keys=True,indent=2)+"\n"

def load_local(path):
    return State.decode(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else State()

def save_local(path,state):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix(path.suffix+".tmp")
    temp.write_text(state.encode(),encoding="utf-8")
    temp.replace(path)

def due(state,now):
    return all(not value or now>=datetime.fromisoformat(value) for value in (state.next_check,state.blocked_until))

def record(state,result,now,config):
    stamp = now.isoformat()
    state.first_run = state.first_run or stamp
    state.last_check = stamp
    state.months = result.months
    state.last_status = result.status.value
    state.captcha = result.captcha
    slot_seconds = config.interval*60
    next_slot = (int(now.timestamp())//slot_seconds+1)*slot_seconds
    state.next_check = datetime.fromtimestamp(next_slot,tz=now.tzinfo).isoformat()
    roll_day(state,now)
    if result.complete:
        state.recovery_pending = state.recovery_pending or state.failures>0
        state.failures = 0
        state.last_error = None
        state.last_success = stamp
        state.daily_successes += 1
        state.blocked_until = None
    else:
        state.failures += 1
        state.last_error = result.error or result.status.value
        if state.last_error=="ACCESS_BLOCKED" or result.retry_after:
            seconds = max(config.cooldown_hours*3600,result.retry_after)
            state.blocked_until = (now+timedelta(seconds=seconds)).isoformat()
    state.notified_dates = sorted(x for x in state.notified_dates if x>=now.date().isoformat())
    state.email_notified_dates = sorted(x for x in state.email_notified_dates if x>=now.date().isoformat())


def roll_day(state,now):
    day = now.date().isoformat()
    if state.day!=day:
        previous = (now.date()-timedelta(days=1)).isoformat()
        state.previous_day_successes = state.daily_successes if state.day==previous else 0
        state.day,state.daily_successes = day,0

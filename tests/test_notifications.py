from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock
import pytest
import requests
import responses
from visa_monitor.models import CheckResult,Status
from visa_monitor.notifications import Telegram,NotificationError,deliver
from visa_monitor.state import State,record

API = "https://api.telegram.org/botTEST_TOKEN/sendMessage"

@responses.activate
@pytest.mark.parametrize("status,payload",[(200,{"ok":False}),(403,{"ok":False}),(200,{"ok":True}),(200,{"ok":True,"result":{}})])
def test_telegram_requires_acknowledgement(status,payload):
    responses.post(API,status=status,json=payload)
    with pytest.raises(NotificationError):
        Telegram("TEST_TOKEN","123").send("fixture")

@responses.activate
def test_telegram_delivered():
    responses.post(API,json={"ok":True,"result":{"message_id":123}})
    Telegram("TEST_TOKEN","123").send("fixture")

@responses.activate
def test_telegram_exception_does_not_expose_token():
    responses.post(API,body=requests.Timeout(API))
    with pytest.raises(NotificationError) as exc:
        Telegram("TEST_TOKEN","123").send("fixture")
    assert "TEST_TOKEN" not in str(exc.value)

@responses.activate
def test_telegram_invalid_json():
    responses.post(API,body="not json")
    with pytest.raises(NotificationError):
        Telegram("TEST_TOKEN","123").send("fixture")

def setup(config,now):
    config = replace(config,dry_run=False,daily_summary=False)
    state = State()
    result = CheckResult(Status.AVAILABLE,["2026-11","2026-12","2027-01"],["2026-11-18"])
    record(state,result,now,config)
    return config,state,result

def test_duplicate_suppression_survives_serialization(config,now):
    config,state,result = setup(config,now)
    sender = Mock()
    assert deliver(state,result,now,config,sender)==["availability"]
    state = State.decode(state.encode())
    assert deliver(state,result,now+timedelta(minutes=15),config,sender)==[]
    assert sender.send.call_count==1
    result.dates.append("2026-12-21")
    assert deliver(state,result,now,config,sender)==["availability"]
    assert "21 December 2026" in sender.send.call_args[0][0]

def test_delivery_failure_not_marked_notified(config,now):
    config,state,result = setup(config,now)
    with pytest.raises(NotificationError):
        deliver(state,result,now,config,Mock(send=Mock(side_effect=NotificationError())))
    assert state.notified_dates==[]

def test_dry_run_sends_nothing(config,now):
    _,state,result = setup(config,now)
    sender = Mock()
    assert deliver(state,result,now,config,sender)==[]
    assert state.notified_dates==[] and not sender.send.called

def test_operational_repeated_failure_and_recovery(config,now):
    config = replace(config,dry_run=False,daily_summary=False)
    state,sender = State(),Mock()
    failed = CheckResult(Status.CAPTCHA_FAILED,error="CAPTCHA_FAILED")
    for i in range(3):
        record(state,failed,now+timedelta(minutes=15*i),config)
        deliver(state,failed,now+timedelta(minutes=15*i),config,sender)
    assert sender.send.call_count==1 and "UNKNOWN" in sender.send.call_args[0][0]
    record(state,failed,now+timedelta(hours=1),config)
    deliver(state,failed,now+timedelta(hours=1),config,sender)
    assert sender.send.call_count==1
    success = CheckResult(Status.UNAVAILABLE)
    record(state,success,now+timedelta(hours=2),config)
    assert deliver(state,success,now+timedelta(hours=2),config,sender)==["recovery"]

def test_stale_alert_before_failure_threshold(config,now):
    config = replace(config,dry_run=False,daily_summary=False,failure_threshold=100)
    state = State(first_run=(now-timedelta(hours=7)).isoformat())
    result = CheckResult(Status.NETWORK_ERROR,error="NETWORK_ERROR")
    record(state,result,now,config)
    assert deliver(state,result,now,config,Mock())==["operational"]

def test_daily_health_once(config,now):
    config = replace(config,dry_run=False)
    state,sender = State(),Mock()
    result = CheckResult(Status.UNAVAILABLE)
    record(state,result,now,config)
    assert deliver(state,result,now,config,sender)==["summary"]
    assert deliver(state,result,now,config,sender)==[]
    assert "Successful complete checks today: 1" in sender.send.call_args[0][0]

def test_partial_availability_alert(config,now):
    config,state,result = setup(config,now)
    result.status = Status.PARTIAL_CHECK
    assert deliver(state,result,now,config,Mock())==["availability"]

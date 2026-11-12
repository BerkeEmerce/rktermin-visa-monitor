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

@pytest.mark.parametrize("status",[Status.CAPTCHA_FAILED,Status.NETWORK_ERROR,Status.PARSE_ERROR,Status.ACCESS_BLOCKED,Status.UNAVAILABLE])
def test_non_availability_never_sends_telegram(config,now,status):
    config = replace(config,dry_run=False,daily_summary=True,failure_threshold=1)
    state,sender = State(first_run=(now-timedelta(days=2)).isoformat(),recovery_pending=True),Mock()
    result = CheckResult(status,error=None if status==Status.UNAVAILABLE else status.value)
    record(state,result,now,config)
    assert deliver(state,result,now,config,sender)==[]
    assert not sender.send.called

def test_partial_availability_alert(config,now):
    config,state,result = setup(config,now)
    result.status = Status.PARTIAL_CHECK
    assert deliver(state,result,now,config,Mock())==["availability"]

def test_email_and_telegram_acknowledge_independently(config,now):
    config,state,result = setup(config,now)
    telegram,email = Mock(),Mock(send=Mock(side_effect=NotificationError("email unavailable")))
    with pytest.raises(NotificationError):
        deliver(state,result,now,config,telegram,email)
    assert state.notified_dates==["2026-11-18"]
    assert state.email_notified_dates==[]
    email.send.side_effect = None
    assert deliver(state,result,now,config,telegram,email)==["email"]
    assert telegram.send.call_count==1 and email.send.call_count==2
    assert State.decode(state.encode()).email_notified_dates==["2026-11-18"]

def test_email_still_attempted_when_telegram_fails(config,now):
    config,state,result = setup(config,now)
    telegram,email = Mock(send=Mock(side_effect=NotificationError())),Mock()
    with pytest.raises(NotificationError):
        deliver(state,result,now,config,telegram,email)
    assert state.notified_dates==[] and state.email_notified_dates==["2026-11-18"]
    assert email.send.call_count==1

def test_email_configuration_is_optional_and_private():
    from visa_monitor.notifications import Email
    assert Email.from_env({}) is None
    with pytest.raises(ValueError):
        Email.from_env({"SMTP_HOST":"smtp.example.test"})
    email = Email.from_env({"SMTP_HOST":"smtp.example.test","SMTP_USERNAME":"user",
                           "SMTP_PASSWORD":"SECRET","EMAIL_FROM":"sender@example.test"})
    assert email.recipient=="berkeemerce@gmail.com" and email.port==465
    assert "SECRET" not in repr(email)

def test_smtp_uses_tls_and_does_not_expose_provider_errors():
    from visa_monitor.notifications import Email
    from unittest.mock import patch
    import smtplib
    email = Email("smtp.example.test",465,"user","SECRET","sender@example.test","recipient@example.test")
    with patch("visa_monitor.notifications.smtplib.SMTP_SSL") as factory:
        smtp = factory.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        email.send("Available date")
        assert smtp.login.call_args.args==("user","SECRET")
        assert smtp.send_message.call_args.args[0]["To"]=="recipient@example.test"
        smtp.login.side_effect = smtplib.SMTPException("SECRET")
        with pytest.raises(NotificationError) as error:
            email.send("Available date")
        assert "SECRET" not in str(error.value)

def test_telegram_test_command_is_disabled(monkeypatch,capsys):
    from visa_monitor.main import main
    monkeypatch.setenv("DRY_RUN","true")
    from unittest.mock import patch
    with patch("visa_monitor.main.Telegram.send") as send:
        assert main(["telegram-test"])==2
    assert not send.called

import pytest
import responses

from visa_monitor.config import Config
from visa_monitor.models import CheckError
from visa_monitor.twocaptcha import TwoCaptcha

API = "https://api.2captcha.com/"


@responses.activate
def test_paid_solve_processing_then_ready():
    responses.post(API + "createTask", json={"errorId": 0, "taskId": 123})
    responses.post(API + "getTaskResult", json={"errorId": 0, "status": "processing"})
    responses.post(API + "getTaskResult", json={"errorId": 0, "status": "ready", "solution": {"text": "a1b2c3"}})
    solver = TwoCaptcha("SECRET", sleep=lambda _: None)
    assert solver.recognize(b"image") == "a1b2c3"
    assert len(responses.calls) == 3


@responses.activate
def test_missing_key_never_creates_paid_task():
    with pytest.raises(CheckError, match="secret is missing"):
        TwoCaptcha("").recognize(b"image")
    assert not responses.calls


@responses.activate
def test_creation_failure_never_retries_or_leaks_key():
    responses.post(API + "createTask", json={"errorId": 1, "errorDescription": "SECRET"})
    with pytest.raises(CheckError) as exc:
        TwoCaptcha("SECRET").recognize(b"image")
    assert "SECRET" not in str(exc.value)
    assert len(responses.calls) == 1


@responses.activate
def test_poll_limit_creates_only_one_paid_task():
    responses.post(API + "createTask", json={"errorId": 0, "taskId": 123})
    responses.post(API + "getTaskResult", json={"errorId": 0, "status": "processing"})
    with pytest.raises(CheckError, match="polling limit"):
        TwoCaptcha("SECRET", sleep=lambda _: None).recognize(b"image")
    assert len(responses.calls) == 13


@responses.activate
def test_invalid_solution_and_incorrect_report():
    responses.post(API + "createTask", json={"errorId": 0, "taskId": 123})
    responses.post(API + "getTaskResult", json={"errorId": 0, "status": "ready", "solution": {"text": "<bad>"}})
    solver = TwoCaptcha("SECRET", sleep=lambda _: None)
    with pytest.raises(CheckError, match="invalid answer"):
        solver.recognize(b"image")
    responses.post(API + "reportIncorrect", json={"errorId": 0, "status": "success"})
    solver.report_incorrect()
    assert len(responses.calls) == 3


def test_key_private_and_hourly_configuration():
    assert Config.from_env({}).captcha_mode == "2captcha"
    config = Config.from_env({"CAPTCHA_MODE": "2captcha", "CAPTCHA_API_KEY": "PRIVATE_KEY"})
    assert config.interval == 60 and config.months == 3
    assert config.captcha_api_key == "PRIVATE_KEY"
    assert "PRIVATE_KEY" not in repr(config)


@responses.activate
def test_paid_backend_reaches_calendar_without_local_ocr_permission(fixture, config):
    from dataclasses import replace
    from datetime import date
    from test_calendar import FakeTransport
    from visa_monitor.portal_client import PortalClient

    responses.post(API + "createTask", json={"errorId": 0, "taskId": 123})
    responses.post(API + "getTaskResult", json={"errorId": 0, "status": "ready", "solution": {"text": "abc123"}})
    config = replace(config, captcha_mode="2captcha", captcha_api_key="SECRET")
    transport = FakeTransport([fixture("captcha.html"), fixture("nov_empty.html")])
    client = PortalClient(config, transport)
    assert isinstance(client.ocr, TwoCaptcha)
    client.ocr.sleep = lambda _: None
    client.open_calendar(date(2026, 11, 1), date(2026, 11, 12))
    assert client.metrics["accepted"] == 1

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from archive_nicosia_run import report


def metadata(conclusion="success", event="schedule", attempt=1):
    return {"id": 12345, "run_attempt": attempt, "event": event,
            "created_at": "2026-11-12T13:27:00Z", "updated_at": "2026-11-12T13:28:00Z",
            "conclusion": conclusion, "repository": {"full_name": "BerkeEmerce/rktermin-visa-monitor"}}


def test_empty_result_is_confirmed_only_with_calendar_success():
    value = report(metadata(), {"status": "ok", "dates": [], "checked_at": "2026-11-12T13:27:30Z"})
    assert value["status"] == "UNAVAILABLE"
    assert value["calendar_checked"] is True
    assert value["source"] == "automatic"


def test_green_workflow_without_result_is_unknown():
    value = report(metadata(), {})
    assert value["status"] == "NOT_RECORDED"
    assert value["calendar_checked"] is False
    assert value["checked_at"] is None


def test_cancelled_run_has_its_own_record():
    value = report(metadata("cancelled", attempt=2), {})
    assert value["status"] == "CANCELLED"
    assert value["id"] == "12345:2"


def test_deployment_is_not_automatic():
    value = report(metadata(event="push"), {})
    assert value["source"] == "manual"
    assert value["trigger"] == "push"

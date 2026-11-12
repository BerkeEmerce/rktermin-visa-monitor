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


def test_external_scheduler_is_automatic():
    run = metadata(event="workflow_dispatch")
    run["display_title"] = "Nicosia check · cron-job.org"
    value = report(run, {"status": "ok", "dates": []})
    assert value["source"] == "automatic"
    assert value["scheduler"] == "cron-job.org"


def test_manual_dispatch_is_not_external_scheduler():
    run = metadata(event="workflow_dispatch")
    run["display_title"] = "Nicosia check · manual"
    value = report(run, {})
    assert value["source"] == "manual"
    assert value["scheduler"] is None


def test_archive_keeps_checked_months_and_normal_navigation_stop():
    result = {"status": "ok", "dates": [],
              "months": [{"month": "2026-11", "checked": True, "dates": []},
                         {"month": "2026-12", "checked": True, "dates": []}],
              "navigation_note": "Tried 2027-01 once; the portal stayed on 2026-12.",
              "coverage": "current month plus up to two next-arrow moves"}
    value = report(metadata(), result)
    assert [m["month"] for m in value["months"]] == ["2026-11", "2026-12"]
    assert value["status"] == "UNAVAILABLE"
    assert value["navigation_note"] == result["navigation_note"]


def test_artifact_reader_keeps_all_five_navigation_snapshots(monkeypatch):
    import io
    import json
    import zipfile
    from unittest.mock import Mock, MagicMock
    import archive_nicosia_run

    result = {"status": "ok", "snapshots": [{"file": f"response-{n:02d}.html"} for n in range(1, 6)]}
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("result.json", json.dumps(result))
        for snapshot in result["snapshots"]:
            archive.writestr("target/snapshots/" + snapshot["file"], "<h2>1/2099</h2>")
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value.read.return_value = payload.getvalue()
    monkeypatch.setattr(archive_nicosia_run, "build_opener", lambda *_: opener)
    history = Mock()
    history.token = "test-token"
    history.call.return_value = {"artifacts": [{"name": "nicosia-result-12345-1", "expired": False,
                                               "created_at": "2026-11-12", "archive_download_url": "https://example.com/artifact"}]}
    restored = archive_nicosia_run.artifact_result(history, metadata(), include_snapshots=True)
    assert len(restored["_snapshot_html"]) == 5
    assert restored["_snapshot_html"]["response-05.html"] == "<h2>1/2099</h2>"

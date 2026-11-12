import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_log",Path(__file__).parents[1]/"scripts/publish_run_log.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ENV = {"GITHUB_REPOSITORY":"owner/monitor","GITHUB_RUN_ID":"123","GITHUB_RUN_ATTEMPT":"1",
       "TIMEZONE":"Asia/Nicosia","MONTHS_TO_CHECK":"3"}
META = {"created_at":"2026-11-12T11:07:00Z","run_started_at":"2026-11-12T11:07:00Z","event":"schedule"}

def test_months_have_distinct_yes_no_and_not_checked_results():
    result = {"status":"PARTIAL_CHECK","months":["2026-11","2026-12"],"dates":["2026-12-18"],
              "captcha":{"accepted":1,"ocr":{"engine":"2captcha"}}}
    report = module.make_report(result,ENV,META)
    assert [row["available"] for row in report["months"]]==[False,True,None]
    assert report["months"][2]["checked"] is False
    assert report["source"]=="automatic" and report["captcha"]["accepted"]==1

def test_skip_never_reuses_previous_months():
    report = module.make_report({"status":"SKIPPED","months":["2026-11"],"dates":["2026-11-18"]},ENV,META)
    assert all(not row["checked"] and row["available"] is None for row in report["months"])

def test_empty_output_is_failure_and_does_not_claim_unavailability():
    report = module.make_report({},ENV,META)
    assert report["status"]=="RUN_FAILED"
    assert all(row["available"] is None for row in report["months"])

def test_report_excludes_raw_secrets_sessions_and_images():
    result = {"status":"UNAVAILABLE","months":["2026-11"],"dates":[],
              "token":"PRIVATE","html":"PRIVATE","reason":"Failed https://example.test/?session=PRIVATE",
              "captcha":{"image":"PRIVATE","accepted":1,"ocr":{"engine":"2captcha","api_key":"PRIVATE"}}}
    import json
    text = json.dumps(module.make_report(result,ENV,META))
    assert "PRIVATE" not in text and "session=" not in text and "api_key" not in text

def test_log_parser_uses_last_recognized_result():
    assert module.parse_result('noise\n{"status":"UNAVAILABLE"}\nmore noise')["status"]=="UNAVAILABLE"

def test_daily_archive_preserves_every_attempt_and_updates_same_attempt():
    class FakeHistory(module.History):
        def __init__(self):
            self.files = {}
        def update(self,path,transform):
            self.files[path] = transform(self.files.get(path))
    history = FakeHistory()
    first = module.make_report({"status":"UNAVAILABLE"},ENV,META)
    history.save(first)
    second = module.make_report({"status":"CAPTCHA_FAILED"},ENV|{"GITHUB_RUN_ATTEMPT":"2"},META)
    history.save(second)
    history.save(second)
    assert len(history.files["run-history/2026-11-12.json"]["runs"])==2
    assert history.files["run-history/index.json"]["days"]==["2026-11-12"]

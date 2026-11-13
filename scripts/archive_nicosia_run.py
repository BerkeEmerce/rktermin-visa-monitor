"""Save every completed Nicosia workflow attempt, including early failures."""
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener

from publish_run_log import History, clean

WORKFLOW = "nicosia-upstream.yml"


class ArtifactRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if urlparse(req.full_url).netloc != urlparse(newurl).netloc:
            redirected.remove_header("Authorization")
        return redirected


def artifact_result(history, metadata, include_snapshots=False):
    artifacts = history.call("GET", f'/actions/runs/{metadata["id"]}/artifacts?per_page=100')["artifacts"]
    artifacts = [a for a in artifacts if a["name"].startswith(f'nicosia-result-{metadata["id"]}') and not a["expired"]]
    # Reruns have distinct artifacts. Never give an earlier attempt's calendar
    # result to a later failed attempt.
    attempt = metadata.get("run_attempt", 1)
    matching = [a for a in artifacts if a["name"] == f'nicosia-result-{metadata["id"]}-{attempt}']
    if not matching and attempt == 1:
        matching = [a for a in artifacts if a["name"] == f'nicosia-result-{metadata["id"]}']
    if not matching:
        return {}
    artifact = max(matching, key=lambda a: a["created_at"])
    request = Request(artifact["archive_download_url"], headers={
        "Authorization": "Bearer " + history.token,
        "Accept": "application/vnd.github+json", "User-Agent": "nicosia-run-history"})
    with build_opener(ArtifactRedirect()).open(request, timeout=30) as response:
        payload = response.read(4194305)
    if len(payload) > 4194304:
        raise ValueError("Oversized result")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entry = archive.getinfo("result.json")
        if entry.file_size > 65536:
            raise ValueError("Oversized result")
        result = json.loads(archive.read(entry))
        if include_snapshots and isinstance(result, dict):
            html = {}
            for snapshot in result.get("snapshots", []):
                name = snapshot.get("file", "")
                if not re.fullmatch(r"response-(?:0[1-9]|1[0-9]|2[0-5])\.html", name):
                    continue
                entry = archive.getinfo("target/snapshots/" + name)
                if entry.file_size > 524288:
                    raise ValueError("Oversized snapshot")
                html[name] = archive.read(entry).decode("utf-8")
            result["_snapshot_html"] = html
    return result if isinstance(result, dict) else {}


def report(metadata, result):
    run_id, attempt = str(metadata["id"]), int(metadata.get("run_attempt", 1))
    started = metadata.get("run_started_at") or metadata["created_at"]
    dates = [d for d in result.get("dates", [])
             if isinstance(d, str) and re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", d)]
    checked = result.get("status") == "ok"
    conclusion = metadata.get("conclusion") or "unknown"
    status = ("AVAILABLE" if dates else "UNAVAILABLE") if checked else (
        "CANCELLED" if conclusion == "cancelled" else "SKIPPED" if conclusion == "skipped" else
        "NOT_RECORDED" if conclusion == "success" else "RUN_FAILED")
    external = (metadata["event"] == "workflow_dispatch" and
                metadata.get("display_title") == "Nicosia check · cron-job.org")
    return {
        "id": f"{run_id}:{attempt}", "run_id": run_id, "attempt": attempt,
        "source": "automatic" if metadata["event"] == "schedule" or external else "manual",
        "scheduler": "cron-job.org" if external else "GitHub schedule" if metadata["event"] == "schedule" else None,
        "trigger": metadata["event"], "started_at": started,
        "checked_at": result.get("checked_at") if checked else None,
        "finished_at": metadata.get("updated_at"), "status": status,
        "dates": dates, "calendar_checked": checked,
        "coverage": clean(result.get("coverage") or "Current portal month"),
        "months": [{"month": m["month"], "checked": m.get("checked") is True,
                    "dates": [d for d in m.get("dates", []) if isinstance(d, str) and re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", d)]}
                   for m in result.get("months", []) if isinstance(m, dict) and re.fullmatch(r"\d{4}-\d{2}", str(m.get("month", "")))],
        "navigation_note": clean(result.get("navigation_note")),
        "captcha_funds_status": result.get("captcha_funds_status") if result.get("captcha_funds_status") in {"usable", "exhausted"} else None,
        "notification_error": clean(result.get("notification_error")),
        "snapshot_manifest": f"snapshots/runs/{run_id}-{attempt}.json" if result.get("snapshots") else None,
        "snapshot_capture_error": clean(result.get("snapshot_capture_error")),
        "workflow_conclusion": conclusion,
        "error": clean(result.get("error")),
        "reason": None if checked else clean(result.get("error") or
                   "No confirmed calendar result. Open the GitHub log for details."),
        "email_configured": False,
        "run_url": f'https://github.com/{metadata["repository"]["full_name"]}/actions/runs/{run_id}/attempts/{attempt}',
    }


def main():
    env = os.environ
    history = History(env["GITHUB_REPOSITORY"], env["GH_TOKEN"], branch="nicosia-history")
    if "--backfill" in sys.argv:
        runs = []
        page = 1
        while True:
            batch = history.call("GET", f"/actions/workflows/{WORKFLOW}/runs?per_page=100&page={page}")["workflow_runs"]
            runs.extend(r for r in batch if r["status"] == "completed")
            if len(batch) < 100:
                break
            page += 1
    else:
        run_id = env["TARGET_RUN_ID"]
        if not run_id.isdigit():
            raise ValueError("Invalid run ID")
        runs = [history.call("GET", "/actions/runs/" + run_id)]
    for metadata in reversed(runs):
        # Save separate entries for each attempt during initial backfill.
        for attempt in range(1, int(metadata.get("run_attempt", 1)) + 1):
            data = metadata if attempt == metadata.get("run_attempt", 1) else history.call(
                "GET", f'/actions/runs/{metadata["id"]}/attempts/{attempt}')
            if data.get("path") != ".github/workflows/nicosia-upstream.yml":
                raise ValueError("Unexpected workflow")
            result = artifact_result(history, data)
            history.save(report(data, result))
            print(f'Archived Nicosia run {data["id"]}, attempt {attempt}')


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Could not archive the run. Live workflow status remains available on the dashboard.")
        sys.exit(1)

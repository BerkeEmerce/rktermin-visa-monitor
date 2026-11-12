"""Archive one workflow attempt in daily JSON files on monitor-state.
Only allowlisted result fields are published. Uses the standard library so an
installation failure can still be recorded after checkout has completed.
"""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

KNOWN = {"AVAILABLE","UNAVAILABLE","CAPTCHA_FAILED","ACCESS_BLOCKED","PARSE_ERROR",
         "NETWORK_ERROR","PARTIAL_CHECK","SKIPPED","CONFIG_OR_DELIVERY_ERROR"}

def clean(value,limit=400):
    if value is None:
        return None
    value = re.sub(r"https?://\S+","[URL omitted]",str(value))
    return value[:limit]

def parse_result(text):
    for line in reversed(text.splitlines()):
        try:
            value = json.loads(line)
        except (ValueError,TypeError):
            continue
        if isinstance(value,dict) and value.get("status") in KNOWN:
            return value
    return {}

def make_report(result,env,metadata,finished=None):
    finished = finished or datetime.now(timezone.utc).isoformat()
    started = metadata.get("run_started_at") or metadata["created_at"]
    checked_at = result.get("checked_at") or started
    local = datetime.fromisoformat(checked_at.replace("Z","+00:00")).astimezone(
        ZoneInfo(env.get("TIMEZONE") or "Asia/Nicosia"))
    months = {x for x in result.get("months",[]) if isinstance(x,str) and re.fullmatch(r"\d{4}-\d{2}",x)}
    dates = sorted({x for x in result.get("dates",[]) if isinstance(x,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",x)})
    status = result.get("status") or "RUN_FAILED"
    # Skips and process failures must never inherit previous check results.
    if status in {"SKIPPED","RUN_FAILED","CONFIG_OR_DELIVERY_ERROR"}:
        months,dates = set(),[]
    entries = []
    count = min(3,max(1,int(env.get("MONTHS_TO_CHECK") or "3")))
    for offset in range(count):
        index = local.year*12+local.month-1+offset
        month = f"{index//12:04d}-{index%12+1:02d}"
        found = [d for d in dates if d.startswith(month+"-")]
        checked = month in months
        entries.append({"month":month,"checked":checked,
                        "available":bool(found) if checked else None,"dates":found if checked else []})
    metrics = result.get("captcha") if isinstance(result.get("captcha"),dict) else {}
    captcha = {key:metrics[key] for key in ("images","submitted","accepted","rejected")
               if isinstance(metrics.get(key),int)}
    engine = metrics.get("ocr",{}).get("engine") if isinstance(metrics.get("ocr"),dict) else None
    if engine in {"2captcha","tesseract","neural"}:
        captcha["engine"] = engine
    run_id,attempt = str(env["GITHUB_RUN_ID"]),str(env.get("GITHUB_RUN_ATTEMPT") or "1")
    if not run_id.isdigit() or not attempt.isdigit():
        raise ValueError("Invalid workflow identity")
    repository = env["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository):
        raise ValueError("Invalid repository")
    errors = result.get("delivery_errors") or {}
    return {
        "id":run_id+":"+attempt,"run_id":run_id,"attempt":int(attempt),
        "source":"automatic" if metadata.get("event")=="schedule" else "manual",
        "mode":env.get("MODE","monitor"),
        "started_at":started,"checked_at":checked_at,"finished_at":finished,
        "status":status,"months":entries,"captcha":captcha,
        "reason":clean(result.get("reason") or (
            "Workflow ended before a result was produced" if not result else None)),
        "error":clean(result.get("error")),
        "notification_error":bool(result.get("notification_error")),
        "delivery_errors":{k:clean(v,100) for k,v in errors.items() if k in {"telegram","email"}},
        "email_configured":bool(result.get("email_configured",bool(env.get("SMTP_HOST")))),
        "run_url":f"https://github.com/{repository}/actions/runs/{run_id}/attempts/{attempt}",
        "screenshot_available":False,
    }

class History:
    def __init__(self,repository,token,branch="monitor-state"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository) or not token:
            raise ValueError("Repository credentials missing")
        self.api = f"https://api.github.com/repos/{repository}"
        self.token = token
        self.branch = branch

    def call(self,method,path,payload=None,missing=False):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.api+path,data=data,method=method,headers={
            "Authorization":"Bearer "+self.token,"Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json",
            "User-Agent":"rktermin-monitor-history"})
        try:
            with urlopen(request,timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code==404 and missing:
                return None
            raise RuntimeError(f"History storage HTTP {exc.code}") from None
        except (URLError,OSError,ValueError):
            raise RuntimeError("History storage request failed") from None

    def update(self,path,transform):
        # Normal monitor execution is serialized by the workflow concurrency group.
        current = self.call("GET",f"/contents/{quote(path)}?ref={quote(self.branch)}",missing=True)
        old = json.loads(base64.b64decode(current["content"]).decode()) if current else None
        value = transform(old)
        payload = {"branch":self.branch,"message":"Archive monitor run [skip ci]",
                   "content":base64.b64encode((json.dumps(value,sort_keys=True,indent=2)+"\n").encode()).decode()}
        if current:
            payload["sha"] = current["sha"]
        self.call("PUT","/contents/"+quote(path),payload)

    def save(self,report):
        day = report["started_at"][:10]  # UTC day for stable archive paths.
        def daily(previous):
            previous = previous or {"version":1,"date":day,"runs":[]}
            if previous.get("version")!=1 or not isinstance(previous.get("runs"),list):
                raise ValueError("Invalid existing run archive")
            rows = {row["id"]:row for row in previous["runs"]}
            rows[report["id"]] = report
            previous["runs"] = sorted(rows.values(),key=lambda row:(row["started_at"],row["attempt"]),reverse=True)
            return previous
        self.update("run-history/"+day+".json",daily)
        def index(previous):
            previous = previous or {"version":1,"days":[]}
            if previous.get("version")!=1 or not isinstance(previous.get("days"),list):
                raise ValueError("Invalid existing archive index")
            previous["days"] = sorted(set(previous["days"])|{day},reverse=True)
            previous["updated_at"] = report["finished_at"]
            previous["email_configured"] = report["email_configured"]
            return previous
        self.update("run-history/index.json",index)

def main():
    try:
        env = os.environ
        history = History(env["GITHUB_REPOSITORY"],env.get("GH_TOKEN",""))
        metadata = history.call("GET","/actions/runs/"+env["GITHUB_RUN_ID"])
        path = Path(env.get("MONITOR_RESULT_FILE","monitor-result.jsonl"))
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        report = make_report(parse_result(text),env,metadata)
        history.save(report)
        print("Run history archived: "+report["id"]+" ("+report["status"]+")")
        return 0
    except (KeyError,ValueError,RuntimeError,OSError):
        # Raw provider exceptions may contain credentials. Never print them.
        print("Run history could not be archived. Inspect this workflow; calendar results are not assumed.")
        return 1

if __name__=="__main__":
    sys.exit(main())

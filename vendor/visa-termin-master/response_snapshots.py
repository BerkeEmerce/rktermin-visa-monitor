"""Best-effort offline evidence capture; never changes the check result."""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Comment

STYLE = """body{font:16px Arial,sans-serif;color:#24352a;background:#fff;margin:35px;line-height:1.6}
.snapshot-label{border-bottom:2px solid #32834f;padding-bottom:15px;margin-bottom:25px;color:#46694e}
h1,h2,h3,h4{line-height:1.3}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ddd}
fieldset{border:1px solid #ddd;padding:18px}a{color:#287c43}p{margin:16px 0}"""


def sanitized_html(html):
    page = BeautifulSoup(html, "html.parser")
    content = page.select_one("#content") or page.body or page
    fragment = BeautifulSoup(str(content), "html.parser")
    for comment in fragment.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    for tag in list(fragment.find_all(True)):
        if tag.name in {"script", "style", "link", "meta", "base", "iframe", "object", "embed", "svg", "input", "textarea", "select", "button"}:
            tag.decompose()
    for image in fragment.find_all("img"):
        src = image.get("src", "").lower()
        image.replace_with(" → " if "go-next" in src else " ← " if "go-previous" in src else "")
    allowed = {"div", "span", "p", "h1", "h2", "h3", "h4", "h5", "table", "thead", "tbody", "tr", "td", "th",
               "b", "strong", "em", "i", "br", "hr", "ul", "ol", "li", "fieldset", "legend", "caption"}
    for tag in list(fragment.find_all(True)):
        if tag.name not in allowed:
            tag.unwrap()
        else:
            tag.attrs = {key: value for key, value in tag.attrs.items()
                         if key in {"colspan", "rowspan"} and str(value).isdigit()}
    body = re.sub(r"(?i);jsessionid=[a-z0-9._-]+", ";jsessionid=[removed]", str(fragment))
    body = re.sub(r"(?i)\b(token|captchaText|password)=[^\s<>\"']+", r"\1=[removed]", body)
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            f'<style>{STYLE}</style></head><body><div class="snapshot-label">'
            '<strong>Rendered snapshot of downloaded portal HTML</strong><br>'
            'Offline rendering · session links, scripts and external resources removed · not a live browser visit'
            f'</div>{body}</body></html>')


def capture(html, result, stage, requested=None, directory=Path("target/snapshots")):
    try:
        directory.mkdir(parents=True, exist_ok=True)
        rendered = sanitized_html(html)
        number = len(result.get("snapshots", [])) + 1
        filename = f"response-{number:02d}.html"
        (directory / filename).write_text(rendered, encoding="utf-8")
        result.setdefault("snapshots", []).append({
            "file": filename, "stage": stage, "requested": requested,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "response_sha256": hashlib.sha256(html.encode()).hexdigest(),
            "render_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        })
    except Exception:
        result["snapshot_capture_error"] = "Snapshot capture unavailable; check results are unaffected."

"""Optional post-check renderer. Only renders saved HTML, with all network blocked."""
import base64
import hashlib
import os
import re
import sys
from urllib.parse import quote

from archive_nicosia_run import History, artifact_result


def main():
    history = History(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"], branch="nicosia-history")
    run_id = os.environ["TARGET_RUN_ID"]
    if not run_id.isdigit():
        raise ValueError("Invalid run ID")
    metadata = history.call("GET", "/actions/runs/" + run_id)
    result = artifact_result(history, metadata, include_snapshots=True)
    html = result.get("_snapshot_html", {})
    if not html:
        print("No saved HTML snapshots for this run.")
        return
    entries = []
    missing = {}
    for snapshot in result.get("snapshots", [])[:25]:
        source = html.get(snapshot.get("file"))
        if not source:
            continue
        digest = hashlib.sha256(source.encode()).hexdigest()
        path = f"snapshots/images/{digest}.jpg"
        exists = history.call("GET", f"/contents/{path}?ref=nicosia-history", missing=True)
        if not exists:
            missing[path] = source
        entries.append({"stage": snapshot.get("stage"), "requested": snapshot.get("requested"),
                        "captured_at": snapshot.get("captured_at"), "response_sha256": snapshot.get("response_sha256"),
                        "image": path})
    if missing:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(java_script_enabled=False, service_workers="block", viewport={"width": 1100, "height": 800})
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            for path, source in missing.items():
                page.set_content(source, wait_until="domcontentloaded", timeout=15000)
                image = page.screenshot(type="jpeg", quality=70, full_page=True, timeout=15000)
                if len(image) > 524288:
                    raise ValueError("Rendered snapshot exceeds size limit")
                history.call("PUT", "/contents/" + path, {
                    "branch": "nicosia-history", "message": "Save rendered portal snapshot [skip ci]",
                    "content": base64.b64encode(image).decode(),
                })
            browser.close()
    manifest = {"version": 1, "run_id": run_id, "attempt": metadata.get("run_attempt", 1),
                "label": "Rendered snapshots of downloaded HTML; no additional portal visits", "snapshots": entries}
    history.update(f'snapshots/runs/{run_id}-{metadata.get("run_attempt", 1)}.json', lambda old: manifest)
    print(f"Saved {len(entries)} snapshot references; rendered {len(missing)} new images.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Optional snapshot rendering failed (" + type(error).__name__ + "). Monitor checks and alerts are unaffected.")
        sys.exit(1)

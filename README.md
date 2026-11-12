# RK-Termin personal visa appointment monitor

**EXPERIMENTAL — cloud workflow and Telegram delivery verified; live calendar access remains unverified.**

Repository setup and state initialization are complete. Recurring experimental checks are enabled while CAPTCHA recognition is being validated. Failed CAPTCHA checks leave availability unknown; no successful automatic calendar check has yet been recorded. See [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md) for the latest measured results; the original validation report is a historical snapshot.

Configured for North Nicosia: `locationCode=niko`, `realmId=926`, `categoryId=1860`, `Asia/Nicosia`. The [official category page](https://service2.diplo.de/rktermin/extern/choose_category.do?locationCode=niko&realmId=926&categoryId=1860&request_locale=en) confirms this office and describes tourist visa appointments. This category is not the long-stay visa route. The software does not reserve appointments and never requests applicant information.

See [START_HERE.md](START_HERE.md) for setup and [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for what has actually been verified.

The optional CPU-only neural backend is selected with `OCR_ENGINE=neural` and installed with `python -m pip install '.[neural]'`. It uses both packaged MIT-licensed ddddocr models locally, without a paid API or runtime model download, and requires exact agreement between their readings. `CAPTCHA_EXPECTED_LENGTH=6` validates the output format. The model score is a heuristic; only an accepted server response followed by calendar evidence establishes success. One unreadable image can be refreshed through the portal's own form; the two-image/two-answer ceiling still applies. Tesseract remains available through `OCR_ENGINE=tesseract`. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## What the implementation does

Each execution starts a fresh `requests.Session`, consults robots.txt, loads the month page and terminates after at most the configured current-plus-two-month horizon. It uses local time in Asia/Nicosia. It preserves cookies, the CAPTCHA form's action including `;jsessionid`, hidden tokens and the calendar dispatch button. Month changes follow the page's actual navigation links; it never synthesizes independent next-month requests or opens an appointment form.

Dates require same-origin `appointment_showDay.do` links for the configured category and displayed month. Past dates and disabled links are ignored. The parser supports English/German month names and numeric month/year headings, including the historical RK-Termin list layout. Empty results require a recognized calendar structure, or the exact no-availability message together with a displayed month and adjacent month navigation in the portal content region. An entire complete month grid without links can also establish an empty result. Unknown controls, contradictory evidence, missing headings and expired sessions fail closed. Current North Nicosia calendar markup is still unverified and may need an adapter update.

| Status | Meaning |
| --- | --- |
| `AVAILABLE` | All requested months checked; at least one bookable date link found |
| `UNAVAILABLE` | Every requested month successfully checked; no eligible dates |
| `CAPTCHA_FAILED` | CAPTCHA required, disabled, rejected, unreadable or expired |
| `ACCESS_BLOCKED` | Denied/rate-limited response, robots prohibition or denial page |
| `PARSE_ERROR` | Unexpected page, target mismatch or unsupported navigation |
| `NETWORK_ERROR` | Transport/timeout/server failure |
| `PARTIAL_CHECK` | At least one month checked, then a failure; dates from checked months remain usable |

A failed check is never printed or alerted as no appointments. Confirmed dates from a partial check can trigger an alert; the alert identifies the partial status. The output includes the underlying error, inspected months and CAPTCHA counters, without raw pages, session URLs, cookies or credentials.

## Installation and local commands

Python **3.12+** is required. From the project directory:

```sh
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install '.[test,ocr]'
python -m pytest -q
python -m visa_monitor.main diagnostic
```

Diagnostic mode never sends Telegram notifications or updates persistent state, even if DRY_RUN=false. It contacts the live portal with normal respectful request bounds and, by default, stops at CAPTCHA. Exit code 0 means all months were checked; 1 means failed/partial; 2 means configuration, state-storage or delivery setup error. A run skipped by the due-time/cooldown gate exits 0 unless a health notification fails; its explicit status is `SKIPPED`.

For a local dry run using a local JSON state file:

```sh
python -m visa_monitor.main check --state state.json
```

Export environment variables in your shell; `.env.example` is a reference and is not loaded automatically. Never commit a populated environment file. Leave `AUTO_BOOK=false`; true is rejected and no booking code exists.

## CAPTCHA feasibility and limits

The live CAPTCHA observed on 12 November 2026 was an embedded 300×50 JPEG. The form ID `appointment_captcha_month`, calendar dispatch action and hidden field layout matched the adapter. One image was inspected privately; no real image, cookie or session token is in this repository. No server answer was submitted. Successful access to the CAPTCHA is not successful access to the calendar.

`CAPTCHA_MODE=disabled` is the safe default. If the portal's applicable access policy permits automated local OCR, set `OCR_PERMISSION_CONFIRMED=true` and `CAPTCHA_MODE=ocr` for a controlled diagnostic. This flag records an operator decision; it is not evidence that permission exists. Neither robots.txt nor silence in generic terms establishes CAPTCHA automation permission.

The optional pipeline uses Pillow grayscale/resizing, OpenCV Otsu/adaptive thresholding and morphology, then Tesseract PSM 7 and 8. At most eight local recognition passes vote for **one** candidate per image. A minimum of two agreeing readings is a heuristic, not calibrated confidence. At most two server submissions occur per execution. Repeated identical challenges stop; unreadable images stop; CAPTCHA POSTs are never retried after a transport failure. No proxy rotation, browser impersonation, fingerprint evasion, paid APIs, external AI or brute-force enumeration is used. OCR exceptions become `CAPTCHA_FAILED`.

Ubuntu OCR dependencies:

```sh
sudo apt-get update
sudo apt-get install -y tesseract-ocr
python -m pip install '.[ocr]'
```

Recognition and server acceptance are separate metrics. For representative, privately collected and permitted samples, create a private JSON manifest outside the repository:

```json
[
  {"image":"sample01.png","expected":"manually transcribed label","server_accepted":null}
]
```

Then run `python scripts/evaluate_ocr.py /private/path/manifest.json`. Boolean `server_accepted` must come from an observed, correctly paired server response, not a guessed reading. The command reports exact recognition and observed acceptance separately. Per-run diagnostic counters record recognized/submitted/accepted/rejected challenges. Acceptance is counted only after a valid calendar is parsed. Evaluate samples across different times and sessions, keep the denominator, and record all failures. One sample, a mocked OCR test, or one successful solve cannot establish reliability. If the live policy or CAPTCHA makes this infeasible, keep OCR and scheduling disabled and treat monitoring as blocked.

## Telegram setup and delivery

1. In Telegram, open verified **@BotFather**, send `/newbot` and follow the prompts.
2. Keep its token private. Open your new bot and send `/start`.
3. On your local shell, run `python scripts/telegram_chat_id.py` and paste the bot token at its hidden prompt. An existing `TELEGRAM_BOT_TOKEN` environment variable is also supported. It prints chat IDs only, not message bodies or tokens, and does not save the token. Run this locally rather than in public Actions logs. Alternatively inspect the official `getUpdates` response privately. Existing webhooks can prevent getUpdates; use a dedicated bot.
4. Save token and chat ID in the repository's **Settings → Secrets and variables → Actions → Secrets** as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
5. Test with Actions mode `telegram-test`, or locally:

```sh
python -m visa_monitor.main telegram-test
```

The explicit test command sends one real test message regardless of DRY_RUN; its text does not claim calendar monitoring works. The notifier checks HTTP status, Bot API `ok=true` and a returned message ID. Token-containing raw exceptions are suppressed. A Telegram network error can leave delivery ambiguous; no automatic immediate resend is performed.

Actual availability messages use dates parsed from the portal and include local check time, location, category, status and the official category entry link. A new CAPTCHA may be needed when booking. Messages are plain text and contain no applicant details.

## Persistent state and alert behavior

Cloud state is `state.json` on the `monitor-state` branch, accessed with the run-scoped `GITHUB_TOKEN` and Contents API. It contains only check times, category identity, checked months, notified dates, daily counters, failures, next due/cooldown times and notification metadata. No state artifacts/caches, CAPTCHA images, cookies or Telegram secrets are saved. A separate bounded dependency cache contains public Python package downloads only; it is saved before portal checking so an expected CAPTCHA failure does not force another model download. The initial state branch is based on the source commit; subsequent commits update the JSON file. Both monitor and CI workflows prevent state-branch executions.

The workflow serializes runs. State writes use the file's SHA for conflict detection and occur before notifications and again after delivery acknowledgements. Missing/corrupt/unreadable state fails closed before contacting the portal; it never silently resets deduplication. Only the first manual monitor execution may use `initialize_state=true`. Do not delete the state branch to fix a transient error. Branch protection must allow the workflow token to write this branch. State failures appear as failed Actions runs; notification cannot be safely guaranteed when storage or Telegram is unavailable.

New dates alert immediately. Acknowledged dates are remembered across runner sessions and complete unavailability results; genuinely new dates alert again. Past dates are pruned. No recurring availability reminders are enabled. Reappearing previously notified dates are suppressed. This avoids routine duplicates but is **at-least-once**, not exactly-once: a crash or failed final state write after Telegram accepts a message can cause a later duplicate.

After three consecutive failures, the monitor alerts with unknown availability. Parse errors and access blocks alert immediately. `STALE_AFTER_HOURS` checks for a prolonged lack of complete checks while executions still run. Operational alerts are throttled with `OPERATIONAL_ALERT_HOURS`; recovery alerts wait for all requested months to succeed. A daily summary includes last complete success, today's complete checks and yesterday's count. Summaries still run during an access cooldown. Failed notification history is preserved for retry in a later run.

**A stopped scheduler cannot notify about its own silence.** GitHub downtime, disabled workflows, account problems or inactivity suspension can prevent all checks and health messages. An absent daily summary is a useful warning; this architecture cannot guarantee an independent outage alert.

## Scheduling and access restrictions

`7,22,37,52 * * * *` schedules roughly every 15 minutes in UTC, including weekends. GitHub may delay or drop scheduled executions. The project uses an eight-minute job limit and `concurrency` with `cancel-in-progress=false`. GitHub may replace an older pending run when multiple runs queue; overlapping execution is prevented.

`CHECK_INTERVAL_MINUTES` accepts positive multiples of 15. It throttles actual portal checks using persisted time slots so small runner startup differences do not halve the frequency. Changing it does not change GitHub's cron or number of runner startups. To reduce Actions startups, also edit `.github/workflows/monitor.yml`: for 30 minutes use `7,37 * * * *`, for hourly use `7 * * * *`. Do not shorten below the configured interval or the portal's permitted frequency.

Requests are at least three seconds apart, honor robots Crawl-delay/Request-rate and use a clearly identified user agent. GET failures retry at most twice with bounded backoff. POSTs do not retry. HTTP 401/403/429 stops immediately and persists at least 24 hours of cooldown, extended by Retry-After. Server Retry-After is also preserved across runs. Disallowed robots URLs are never requested. Unknown robot responses, redirects to unfamiliar steps or unsupported controls stop the check. No TLS validation is disabled.

## Deployment procedure

1. Create an empty **public** repository in your GitHub account. Preserve `.github`, `.gitignore`, source, fixtures, LICENSE and NOTICE when pushing this folder. Do not upload `work/`, real samples or secrets. `scripts/deploy.ps1` automates creation/push and secret prompts with Git and GitHub CLI.
2. Open **Actions**, enable repository workflows if prompted and confirm **Tests** passes. The cloud CI matrix targets Python 3.12 and 3.13; local validation used 3.12.
3. Create the Telegram bot and obtain the chat ID as above.
4. Add the two **Actions secrets**. The supplied workflow grants `contents: write`; organization policy must permit it. No personal GitHub access token is required by cloud runs.
5. Run **Visa appointment monitor → Run workflow → telegram-test**. Confirm receipt on your iPhone; review its log.
6. Run mode **diagnostic** with default OCR disabled. Review the explicit status. Do not equate a red CAPTCHA run with zero appointments.
7. Establish whether automated verification and the proposed cloud use are permitted. If permitted, set the OCR repository variables and run bounded diagnostics, recording representative recognition/acceptance results. Confirm displayed months, dates and session-preserving navigation for all three months. Current-category live fixtures must be sanitized before adding to tests.
8. Only once monitoring is viable, run mode **monitor**, checking **initialize_state** once. Confirm the state branch is created, all three months succeed, Telegram works, and a second run preserves deduplication. Use synthetic tests to simulate availability without creating a booking.
9. Enable scheduled executions by setting repository **Actions variable** `MONITOR_ENABLED=true`. Review logs and **Settings → Billing and licensing → Usage** monthly. Keep the repository public, standard Ubuntu runner and $0 budgets for paid products. No state artifacts are generated. The Python dependency download cache was about 173 MiB in the measured run; it contains no runtime state or credentials and is subject to GitHub cache eviction.
10. To stop, set `MONITOR_ENABLED=false` or disable **Visa appointment monitor** under Actions. Delete/revoke the Telegram bot token when no longer needed. Preserve state if you intend to resume.

Public repositories' scheduled workflows can be suspended after 60 days without repository activity. Do not assume automated state commits exempt you; check GitHub's notice and re-enable manually. Do not add activity-spam keepalive jobs. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Costs, terms and practical limits

A 15-minute cron has **2,880 starts per 30 days** (2,976 per 31 days). Estimated normal runtime is 1–3 minutes/run without installing OCR and 2–5 with OCR installation and recognition: about 2,880–8,640 or 5,760–14,400 runner-minutes per 30 days respectively. These are planning estimates, not cloud measurements. The eight-minute cap bounds a 30-day schedule at 23,040 runner-minutes. Actual portal attempts reduce during cooldowns, but setup steps still run. Measure the first cloud runs and revise.

Standard GitHub-hosted runners in public repositories currently have free compute; private GitHub Free has 2,000 monthly minutes, so even one minute per 15-minute start exceeds it. Both workflows therefore refuse private repositories. Larger paid runners are not used. State is a small Git file; there are no recurring state artifacts or per-run cache keys. A fixed dependency-cache key per dependency version uses about 173 MiB in the measured run, below the default free cache allowance. Credentials remain Actions secrets. This project has no paid integration or subscription dependency. See [GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

**Free compute is not permission for production hosting.** GitHub's [additional terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions) restrict Actions use to developing/testing applications and limit unrelated hosted-runner activities. Continuous personal monitoring may fall outside that scope. This package supplies experimental diagnostic/test workflows, but approved permanent hosting has not been established. The 24/7 zero-cost requirement is therefore unresolved independently of CAPTCHA reliability. Do not assume that making a repository public establishes allowed production use. If GitHub does not permit the intended workload, these constraints need a different approved free execution environment; none is silently substituted here.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| CAPTCHA_FAILED | OCR is disabled, unreadable, rejected or session expired. Availability is unknown. Review feasibility, not retry counts. |
| PARSE_ERROR | Do not loosen checks until empty pages pass. Inspect a private sanitized live page and update the adapter/fixtures. |
| ACCESS_BLOCKED / 429 | Respect saved cooldown and Retry-After; do not change identity or use proxies. |
| NETWORK_ERROR | Check later logs; do not turn off HTTPS verification or classify the failure as unavailable. |
| Missing state | Initialize once only for a new deployment. Investigate missing/deleted state before any reset. |
| GitHub state 403/409 | Check token permissions/branch policy or overlapping writers; preserve existing state. |
| Telegram error | Check bot token, /start, chat ID and whether the bot was blocked. State does not mark unacknowledged dates delivered. |
| No scheduled runs | Confirm default branch, MONITOR_ENABLED=true, Actions enabled and GitHub inactivity/account notices. |
| No daily summary | Check Actions and Telegram manually; a stopped workflow cannot alert independently. |

## Architecture and upstream

`config.py` validates environment; `portal_client.py` owns HTTP/session/CAPTCHA navigation; `captcha.py` contains optional OCR; `calendar_parser.py` interprets evidence; `availability.py` checks the month horizon; `state.py`/`github_state.py` persist progress; `notifications.py` formats/delivers alerts; `main.py` orchestrates and exposes commands.

The reference project [rashidisayev/visa-termin-master](https://github.com/rashidisayev/visa-termin-master) was inspected at commit `6d5b967badc20d6d1f7e091deb8139b380044c41`. Its form/session insights and documented endpoint patterns inform this implementation. Its paid solver, curl/file-based request pipeline, one-month control flow, applicant/booking modules and Telegram delivery detection were replaced. A sanitized historical calendar fixture is adapted from upstream. Upstream PolyForm Noncommercial license and full NOTICE, including historical MIT attribution, are retained. This adaptation is for noncommercial use only; it is not a commercial booking service.

Useful primary references: [Tesseract preprocessing](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html), [Telegram Bot API](https://core.telegram.org/bots/api), [RK-Termin usage/privacy conditions](https://service2.diplo.de/rktermin/extern/dsgvo.do?request_locale=en). No generic conditions inspected established affirmative permission for unattended CAPTCHA automation.

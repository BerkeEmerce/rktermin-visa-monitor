# North Nicosia visa appointment monitor

Checks Germany visa appointments for North Nicosia (location niko, realm 926,
category 1860). It checks the current month, then follows the portal's next-month
navigation at most twice. Months the portal does not expose are **Not checked**,
never reported as empty. It does not book appointments.

## Current operation

- GitHub Actions runs hourly at minute 23, independently of your computer.
- Configuration changes to the monitor workflow also trigger a deployment check.
- The default branch must be public and the Actions variable MONITOR_ENABLED
  must equal true for scheduled/deployment runs.
- 2Captcha solves at most two challenges per execution, using CAPTCHA_API_KEY.
- Telegram sends **new appointment availability alerts only**. Health summaries,
  failures, recovery messages and the old Telegram-test command are disabled.
- Optional email alerts go to berkeemerce@gmail.com. They require authenticated
  SMTP sender credentials; see [EMAIL_SETUP.md](EMAIL_SETUP.md).
- Telegram and email acknowledge independently. A failure in one channel does
  not stop the other from being attempted or cause duplicate alerts in it.
- Errors remain visible in run history and Actions. No appointment alert is
  generated for a failure, cooldown, missing month or empty calendar.

A live check on 12 November 2026 accepted a 2Captcha answer, checked November
and December, and found no dates. The portal did not advance to January.
That successful manual execution does not by itself prove subsequent scheduled
runs have executed.

## Dashboard and durable history

[dashboard/](dashboard/) contains a minimal responsive website with:

- date/time in Europe/Berlin and automatic/manual run labels;
- Yes/No appointment results per successfully checked month;
- Not checked for unavailable/unreached months and failed/skipped executions;
- expandable CAPTCHA counters, errors, dates and links to the original run;
- visible warnings when automatic runs are overdue.

The website source is ready but publication to an owner-private chatgpt.site
Site is pending an available execution workspace. No live Site URL is claimed.
Calendar screenshots are not captured by this HTTP monitor or simulated.

Each new workflow attempt is archived on the monitor-state branch under
run-history/YYYY-MM-DD.json with an index at run-history/index.json. There is
no rolling deletion of these records. The final archive step runs even after
an earlier step fails, provided checkout completed and the runner remains alive.
Hard cancellations/outages can prevent it; the dashboard also reads recent
Actions metadata and shows missing results explicitly. Old per-month results
are not reconstructed from guesses.

Only non-sensitive check metadata is archived. Tokens, cookies, sessions, CAPTCHA
images and raw portal pages are excluded. The repository is public; the future
website's private access does not change visibility of this existing source/data
repository.

## Manual run

Repository **Actions > Visa appointment monitor > Run workflow**:
choose monitor (default). Leave initialize_state false for this established
deployment. Diagnostic checks do not send alerts or update deduplication state;
they are identified separately in history.

Do not delete state or initialize again to fix a failed check. State contains
notified dates for each channel and prevents repeated alerts.

To stop monitoring, set MONITOR_ENABLED=false or disable the workflow.
GitHub may delay/drop scheduled runs or suspend inactive workflows. No service
here guarantees instant detection, and a stopped scheduler cannot report itself.

## Development

Python 3.12 or newer:

```sh
python -m pip install '.[test,ocr]'
python -m pytest -q
node --check dashboard/dist/app.js
```

Source modules separate configuration, bounded HTTP/session navigation,
CAPTCHA solving, calendar parsing, notifications and durable state. Tests use
sanitized fixtures and mocked delivery; no real booking or email is created.

Requests preserve session/form navigation, respect denial/rate-limit cooldowns,
and never disable TLS verification or switch identities. Paid 2Captcha usage
requires balance. Hosting terms and original deployment investigations are
retained in [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md); older notes describe
earlier revisions and are not current configuration instructions.

This noncommercial adaptation retains LICENSE, NOTICE and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

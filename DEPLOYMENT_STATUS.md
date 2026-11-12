> **Live validation passed:** [run 43204998592](https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43204998592) checked November and December 2026, found no available dates, then stopped normally when navigation did not advance beyond December. January was not reported as checked or empty. Two paid CAPTCHA answers were submitted: one rejected, one accepted. Result UNAVAILABLE, error null. Hourly monitoring and 2Captcha are enabled. There are 121 passing local tests. Prior deployment notes below are historical.

> **Latest live 2Captcha result:** run [43203615815](https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43203615815) submitted one paid answer; the CAPTCHA disappeared, but calendar parsing failed with Ambiguous month navigation. One follow-up [43204009433](https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43204009433) had the same outcome. Cookie-session and locale link equivalence handling plus safe diagnostic details were subsequently pushed, with 118 local tests passing. Those last changes have not had a live solve yet. No complete three-month availability check is claimed. The user has supplied the secret and enabled hourly checks.

> **Current update: hourly schedule + paid 2Captcha integration.** Local/API tests cover the new backend; live validation is pending the CAPTCHA_API_KEY secret. Recurring checks are paused until you run `scripts/enable-2captcha.ps1`. Existing Telegram/state setup is retained. See [TWOCAPTCHA_SETUP.md](TWOCAPTCHA_SETUP.md). Earlier OCR and zero-cost deployment notes below are historical.

# Deployment and live validation — 12 November 2026

**Experimental: repository/cloud notifications/state work; live calendar access has not succeeded.**

Repository: https://github.com/BerkeEmerce/rktermin-visa-monitor

- GitHub Actions executes independently of the applicant's computer on public standard Ubuntu runners.
- Telegram's API confirmed delivery of a real test message: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43135450980 .
- A real monitor execution initialized the `monitor-state` branch, persisted a CAPTCHA failure and confirmed delivery of its daily health message: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43138810618 . Its result was CAPTCHA_FAILED, not UNAVAILABLE. The JSON state contains no secrets, images, session URLs or cookies.
- The local suite has **109 passing tests**. Cloud CI confirmed 109 passing tests on each of Python 3.12 and 3.13: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43138810181 . Workflow lint passes.
- `CAPTCHA_MODE=ocr` and `OCR_ENGINE=neural` select local CPU inference. Both packaged OCR models must agree on a correctly formatted reading. At most two images are inspected per check, and at most two answers can be submitted. One unreadable image can use the portal's normal refresh dispatch.
- The real refresh response changed the form action to `appointment_refreshCaptchamonth.do`. This observed action is now supported and regression tested; booking actions remain prohibited.

## Actual OCR evidence

1. Tesseract cloud diagnostic: one image, no reliable candidate, zero answers submitted: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43135998552 .
2. Initial single-model neural cloud diagnostic: two images, two answers submitted, **two rejected**: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43137389480 .
3. A local development check submitted one neural reading; the server explicitly returned “The entered text was wrong”. This makes the measured automatic answer total **0 accepted / 3 submitted**, not a claim about all possible OCR methods or a representative benchmark.
4. Two-model agreement checks have rejected uncertain candidates without submitting them. The initialized cloud run inspected two images, refreshed once, submitted zero guesses, and failed safely.
5. Separate manually reviewed development checks are never counted as automatic OCR success. A human-verified sample is needed to independently validate the session/form path and obtain a ground-truth label.

Model confidence values near 0.98 were observed on rejected answers. These scores are not calibrated probabilities of full-string correctness. Increasing a confidence threshold alone does not establish reliability. Offline preprocessing and candidate comparison remain private under `work/`; no real CAPTCHA samples or session captures are published.

## Current settings and limits

`MONITOR_ENABLED=true`: recurring experimental checks are now enabled on the staggered 15-minute cron. This is an ongoing feasibility test, not verified operational appointment monitoring. The latest fresh run inspected two images, refreshed once, submitted no guesses because the models disagreed, persisted its failure, and confirmed delivery of an operational alert: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43197293384 . The latest state still has `last_success=null`. Telegram and state setup do not need repeating. Stop the experiment by setting MONITOR_ENABLED=false.

The initialized cloud monitor/state job completed in 33 seconds; the earlier Tesseract diagnostic completed in 36 seconds. These few runs are not a monthly runtime guarantee. The prepared 15-minute cron means 2,880 starts per 30 days; public standard-runner compute is currently free, while private Free minutes are insufficient even at one billed minute per start. No paid APIs, paid models, proxies, booking automation or larger runners are configured.

The published access instructions were reviewed and robots.txt did not disallow the target during testing. That is not affirmative permission from the portal operator. Denials, rate limits and robots restrictions remain enforced. The GitHub Actions hosting-use limitation in the original report also remains unresolved for permanent production use.

No successful automatic calendar check, actual appointment availability, or 24/7 operational monitoring is claimed. A test that stops at CAPTCHA is not a successful no-availability result.

## Human-assisted sample and cache update

The applicant transcribed one displayed challenge as e44wwd while noting uncertainty about the first two characters. That image was created at 02:08 UTC and submitted after 10:05 UTC, about eight hours later. The server rejected it. Its age and uncertain reading make it unsuitable as a verified recognition label or a conclusive session-flow test; it is excluded from automatic success metrics. No further human transcriptions are currently requested.

A Python dependency cache was saved successfully before the failing portal step. Its measured compressed size was 181,590,686 bytes (about 173 MiB). It contains public package downloads only, with a stable key tied to dependency versions. Cookies, session captures, CAPTCHA images, credentials and monitor state are excluded. The three automatic answers submitted in the earlier single-model tests remain rejected; subsequent agreement-gated runs have failed safely without submitting uncertain readings.

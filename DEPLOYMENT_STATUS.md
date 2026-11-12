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

`MONITOR_ENABLED=false`. Recurring checks are deliberately off while recognition remains unverified. The first real monitor state records a failure, not zero appointments. Telegram and state setup do not need repeating.

The initialized cloud monitor/state job completed in 33 seconds; the earlier Tesseract diagnostic completed in 36 seconds. These few runs are not a monthly runtime guarantee. The prepared 15-minute cron means 2,880 starts per 30 days; public standard-runner compute is currently free, while private Free minutes are insufficient even at one billed minute per start. No paid APIs, paid models, proxies, booking automation or larger runners are configured.

The published access instructions were reviewed and robots.txt did not disallow the target during testing. That is not affirmative permission from the portal operator. Denials, rate limits and robots restrictions remain enforced. The GitHub Actions hosting-use limitation in the original report also remains unresolved for permanent production use.

No successful automatic calendar check, actual appointment availability, or 24/7 operational monitoring is claimed. A test that stops at CAPTCHA is not a successful no-availability result.

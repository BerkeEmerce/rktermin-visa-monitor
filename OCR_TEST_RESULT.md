# Live OCR diagnostic — 12 November 2026

This is the historical first Tesseract run. See [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md) for later neural OCR tests and cloud state validation.

OCR is now enabled in the GitHub repository configuration. Scheduled monitoring remains explicitly disabled (`MONITOR_ENABLED=false`).

Run: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43135998552

The Ubuntu job installed Tesseract and the local OCR dependencies successfully. It then retrieved one live CAPTCHA image. The OCR pipeline returned no reliable candidate. It submitted no CAPTCHA answers and accessed no calendar months. The job correctly returned CAPTCHA_FAILED, not UNAVAILABLE.

Observed counters: images=1, recognized=0, submitted=0, accepted=0, rejected=0. There is no representative labeled dataset, so recognition accuracy is not measurable. Server acceptance rate is also not measurable because there were zero submissions.

The run lasted 36 seconds. A single diagnostic does not establish reliable runtime or production feasibility. The earlier cloud Telegram test succeeded, and Telegram's API confirmed delivery: https://github.com/BerkeEmerce/rktermin-visa-monitor/actions/runs/43135450980 .

Before this bounded diagnostic, the target's robots.txt rules were checked and did not disallow the request. The published category and usage instructions were reviewed; neither explicitly addressed OCR. That review does not constitute affirmative permission from the portal operator. Website blocks and rate limits remain enforced, and no proxy or booking was used.

This is still experimental. The current OCR pipeline has not passed a live calendar-access check. No periodic monitoring or notification of actual availability is claimed.

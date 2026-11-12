# Validation report — 12 November 2026

**Overall: EXPERIMENTAL / BLOCKED FOR UNATTENDED PRODUCTION. Not deployed.**

## Delivered functionality

Executable Python 3.12 package, session-based HTTP client, optional fully local OCR, strict current-plus-two-month parsing, actual-link month navigation, bounded GET retries, no-replay CAPTCHA POSTs, robots/rate-limit handling, Telegram notifications and operational summaries, persistent GitHub branch state, notification deduplication, cloud/manual workflows, deployment helper, fixtures, tests and operating documentation. No booking implementation, applicant-data requirement or paid dependency exists.

## Automated results

- **98 tests passed** on CPython 3.12.16 on Windows; no skipped tests.
- Test coverage includes exact no-availability text, available day links, missing/contradictory evidence, numeric/name month formats, a sanitized historical RK-Termin layout, three-month navigation, December/January transitions, expired sessions, CAPTCHA rejection bounds, no false acceptance on CAPTCHA disappearance, network timeouts, 401/403/429, Retry-After, robots delays/disallow rules, cookie-preserving redirects, malformed HTML, changed calendar controls, Telegram API/delivery errors, deduplication across serialized state, GitHub state initialization/corruption/CAS conflict, recovery alerts, daily summaries during cooldowns and scheduler jitter.
- **actionlint v1.7.12** validated both workflows with exit code 0 and no findings. Shellcheck/pyflakes integrations were disabled because this was a Windows validation environment.
- Dependency consistency check passed for all 22 packages in the isolated development environment.
- Cloud CI defines Python 3.12 and 3.13 on Ubuntu. Neither cloud runner environment nor the 3.13 matrix was executed here.
- OCR preprocessing/voting was exercised on a synthetic image with a mocked Tesseract result. This is a pipeline test, not evidence of recognition accuracy. No local Tesseract executable was installed or real OCR inference run.

## Upstream investigation

Reference: https://github.com/rashidisayev/visa-termin-master at commit `6d5b967badc20d6d1f7e091deb8139b380044c41`.

Its useful findings were normal server-side form navigation, preservation of `;jsessionid`, hidden fields/dispatch buttons, and showDay link patterns. Its one-month limitation, paid solver, file/curl-based sessions, booking modules and Telegram acknowledgement handling were unsuitable for these requirements. New modular implementations replace them. A December 2019 calendar fixture was sanitized/adapted as a format regression case. LICENSE and full NOTICE, including historical MIT attribution, are included. No upstream cookies, images or applicant information are shipped.

## Live portal observations

1. The first web-reader attempts could not access the target month URL. A direct request using the machine's Python 3.11 environment then failed with a TLS EOF before returning HTML. TLS verification was never disabled.
2. A later live diagnostic using the isolated Python 3.12 environment successfully consulted robots.txt and reached a CAPTCHA at the configured current-month URL. With OCR disabled, it returned `CAPTCHA_FAILED`, with zero inspected months and zero dates. It did not report UNAVAILABLE.
3. One further bounded inspection retrieved the CAPTCHA form in a fresh session. Form ID: `appointment_captcha_month`; method: POST; endpoint: `appointment_showMonth.do`; dispatch: `action:appointment_showMonth`. Hidden token/target fields were present. The adapter matched this structure.
4. One embedded JPEG CAPTCHA was inspected privately: **300 × 50 pixels, 5,338 bytes**. The image is distorted and overlapping. Its appearance alone establishes no OCR success rate. No image or real session data is included in deliverables.
5. **No CAPTCHA answer was submitted. No current calendar was accessed. Persistence of verification across month changes was not established.** Calendar/session behavior is covered by mocked tests and a sanitized historical upstream fixture, not a current North Nicosia calendar.
6. The official category page confirmed North Nicosia office and identifiers `niko / 926 / 1860`: https://service2.diplo.de/rktermin/extern/choose_category.do?locationCode=niko&realmId=926&categoryId=1860&request_locale=en . Its description concerns tourist visas; this is not the long-stay route.

Live-request scope was limited to the target portal/category pages and robots.txt. No proxy, fingerprint evasion, account login, booking form or reservation was used.

## CAPTCHA measurement

| Metric | Observed result |
| --- | --- |
| Live image samples inspected | 1 |
| Representative labeled dataset | Not collected |
| Real OCR recognition attempts | 0 |
| Server verification submissions | 0 |
| Confirmed accepted CAPTCHAs | 0 |
| Recognition success rate | **Not measurable** |
| Server acceptance rate | **Not measurable (0 submissions)** |

Zero submissions is not a 0% acceptance rate. No affirmative permission for automated CAPTCHA verification was established from the inspected generic/category conditions. The implementation keeps OCR disabled and records unknown availability. If permission and reliable acceptance cannot be established, the requested unattended monitoring cannot meet its acceptance criteria.

## Cloud and cost assessment

The 15-minute cron represents **2,880 runner starts per 30-day month**, 2,976 for 31 days. Estimated runtime: 1–3 minutes/start without OCR installation, 2–5 with OCR installation/recognition. Corresponding 30-day use: about **2,880–8,640** or **5,760–14,400 runner-minutes**; these are estimates, not cloud benchmarks. The eight-minute per-job cap bounds 30 days at 23,040 runner-minutes. Cooldowns reduce portal attempts but not scheduled setup starts.

GitHub's current billing documentation makes standard public-repository hosted-runner compute free. A private GitHub Free repository's 2,000 monthly minutes cannot support this schedule even at one minute/start. Both workflows explicitly require a public repository and standard Ubuntu runners. No recurring Actions artifacts/caches or paid integrations are configured. Small state snapshots live in Git history, not ephemeral caches. Source: https://docs.github.com/en/billing/concepts/product-billing/github-actions .

There is a separate hosting constraint: GitHub's additional terms restrict Actions use to application development/testing and constrain hosted-runner activities unrelated to a software project's production/testing/deployment/publication. Permanent personal monitoring may fall outside allowed use; this is an inference from the terms, not a confirmed hosting approval or denial. Experimental diagnostics/testing can be prepared, but **approved 24/7 production hosting under the requested platform remains unresolved**. Source: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions .

GitHub may delay/drop scheduled jobs and disable public scheduled workflows after 60 days without repository activity. No independent dead-man alert exists: a stopped scheduler cannot send Telegram health messages. Source: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule .

## Deployment state and exact remaining steps

No GitHub repository was provided or created, no GitHub authenticated integration was available, and the browser-control runtime failed to initialize. GitHub CLI was not installed. No Telegram bot token/chat ID was provided. No credentials were read from unrelated sources. The deliverable includes a setup helper and click-by-click fallback instructions; it is not a deployed service.

1. Sign into GitHub and create/push this package to a public repository using `scripts/deploy.ps1` or README's procedure. Preserve the hidden `.github` directory and license notices.
2. Create a Telegram bot via your account's verified @BotFather, send /start, obtain your chat ID privately, and add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID as Actions secrets.
3. Run manual `telegram-test` and confirm the iPhone receives it. This is the first real delivery validation; mocked successes do not count.
4. Run manual `diagnostic` from GitHub's Ubuntu runner. Review the status without enabling schedules.
5. Establish access-policy permission and viable local OCR; collect representative recognition and paired server-acceptance evidence. If not viable or not permitted, retain the blocked state. Manual CAPTCHA entry does not satisfy unattended cloud execution.
6. Validate a current authorized session across all three real calendar months, displayed month identity and genuine bookable links. Update the adapter if current markup differs. Do not create a booking during validation.
7. Resolve the GitHub hosting-use constraint. Do not equate free public-runner pricing with permitted permanent hosting.
8. Once viable, run manual mode `monitor` with `initialize_state=true` once; inspect the state branch and a subsequent run for persistence/deduplication. All later runs leave initialization unchecked.
9. Set repository variable MONITOR_ENABLED=true to allow the prepared schedule. Review execution usage monthly and scheduler/inactivity notices. Stop through MONITOR_ENABLED=false or disabling the workflow.

The first two account actions require the account holder. Bot credentials should be entered through secret prompts/Actions settings, not posted to this chat or public files. Detailed procedures and troubleshooting are in README.md and START_HERE.md.

## Acceptance status

Source, tests, workflows, configuration, safe statuses, storage logic and notification implementation are delivered. Real Telegram delivery, current calendar parsing, server-verified CAPTCHA success, authorized-session navigation, permitted permanent cloud operation and actual deployment remain **unverified or blocked**. No successful 24/7 appointment monitoring is claimed.

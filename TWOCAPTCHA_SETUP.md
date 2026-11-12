# Hourly checks with 2Captcha

2Captcha solving is ON by default in both Python configuration and the cloud workflow. A funded CAPTCHA_API_KEY is required; a missing key fails safely. Set CAPTCHA_MODE=disabled to turn solving off. The deployed repository already has its API-key secret and hourly monitoring enabled.

The monitor now supports the paid image-solving approach used by https://github.com/rashidisayev/visa-termin-master. Existing Telegram credentials and persistent state are retained. No automatic booking is enabled.

The schedule runs at minute 7 of each hour (GitHub can delay execution). Each run checks the current month and next two months using the portal's navigation and Asia/Nicosia dates.

## Complete setup

From this project's directory, run in your own PowerShell window:

```powershell
.\scripts\enable-2captcha.ps1
```

Paste your funded account's API key into the hidden prompt. The script stores it as GitHub Actions secret CAPTCHA_API_KEY, selects CAPTCHA_MODE=2captcha, enables hourly runs, and starts a live monitor check. It does not create a new repository or Telegram bot.

Only CAPTCHA image bytes are sent to 2Captcha. Portal cookies, hidden fields and session URLs stay in the portal session. No applicant details are requested.

At most two paid tasks are created per execution, with no retries of an ambiguous task creation. One task may suffice for all three months if navigation retains the session. At hourly frequency this means up to 1,440 task creations in 30 days, excluding manual runs; actual charges depend on provider pricing and solve outcomes. No automatic top-up is configured by this project. Polling is bounded and provider errors fail with availability unknown.

The integration has mocked API tests; a live paid solve and accepted three-month calendar check still require your API key. Inspect the actual run result before treating this as operational. Prior OCR results in historical reports do not validate 2Captcha.

Provider API documentation: https://2captcha.com/api-docs/normal-captcha

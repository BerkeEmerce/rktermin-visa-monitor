# Start here

**Status: experimental; not deployed; live calendar access remains blocked by CAPTCHA.**
The source and tests are ready. A live CAPTCHA page was reached and its form/image were inspected. No CAPTCHA answer was submitted, no current calendar was accessed and no Telegram message was sent. This is not operational appointment monitoring yet.

Two account actions require you: GitHub sign-in and creating a Telegram bot in your Telegram account. No payment details, paid service, passport details or applicant data are needed. Keep the bot token private.

## 1. Create your Telegram bot

1. On your iPhone, open Telegram and find the verified **@BotFather** account.
2. Send `/newbot`, then choose a name and an available username ending in `bot`.
3. Save the bot token privately. Do not paste it in a public repository or screenshot.
4. Open your new bot and send `/start`.
5. Obtain your chat ID with `scripts/telegram_chat_id.py` as described in README, or inspect the official Bot API `getUpdates` response privately. No third-party chat-ID bot is needed.

## 2. Publish the prepared repository

The package includes hidden `.github` and `.gitignore` entries; preserve them when extracting/copying.

If you already have Git and GitHub CLI installed, open PowerShell in the extracted `visa-monitor` folder and run:

```powershell
.\scripts\deploy.ps1
```

The helper signs in through GitHub, creates a **public** repository, pushes the project, prompts for the two secrets with hidden input, and runs a Telegram test. It leaves the schedule disabled. Install prerequisites from [Git for Windows](https://git-scm.com/download/win) and [GitHub CLI](https://cli.github.com/) if needed. The script runs only for setup; cloud executions do not use your computer.

If you prefer the GitHub website, follow README's numbered deployment procedure. A repository cannot be created in your account from this chat without an available authenticated connection.

## 3. Validate access before enabling a schedule

Open the repository's **Actions → Visa appointment monitor → Run workflow**, select **diagnostic**, and run it. A red run with `CAPTCHA_FAILED` means availability is unknown. It does not mean appointments are unavailable.

Unattended local OCR is currently disabled. Permission for automated CAPTCHA verification and reliable server acceptance have not been established. Do not enable a production monitor on the strength of passing tests. Read **VALIDATION_REPORT.md**, including the GitHub Actions service-terms limitation.

If a permitted OCR method becomes available, follow README's controlled feasibility test, validate all three months, then initialize state once and enable the schedule. If CAPTCHA remains unreliable or automation is not permitted, the requested unattended zero-cost service cannot be delivered under the current constraints. A human-completed CAPTCHA does not make ephemeral scheduled cloud runs unattended.

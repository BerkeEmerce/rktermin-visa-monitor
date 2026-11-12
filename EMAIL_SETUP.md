# Appointment email alerts

Telegram now sends only new appointment availability alerts. Daily summaries,
failure/recovery messages and the old notification test command are disabled.
Run details and errors go into the dashboard archive.

Email is implemented but remains disabled until an authenticated SMTP sender is
configured. The recipient is berkeemerce@gmail.com, as requested.

In repository Settings > Secrets and variables > Actions > Secrets, add:

| Secret | Value |
| --- | --- |
| SMTP_HOST | Your email provider's SMTP host |
| SMTP_USERNAME | The SMTP account username |
| SMTP_PASSWORD | The provider's SMTP/app password |
| EMAIL_FROM | A sender address authorized for that account |

Set the Actions variable SMTP_PORT to 465 (implicit TLS, default) or 587
(STARTTLS). Do not paste passwords into issues, chats, source files or logs.
No regular mailbox password is required by this project; follow your provider's
instructions for SMTP credentials.

The workflow already supplies the recipient. Do not add an EMAIL_TO secret.
SMTP acknowledgement means the server accepted the message, not that it reached
the inbox. Telegram and email have independent deduplication and failure
tracking, so one failing channel does not prevent the other from being attempted.
If email is unconfigured, Telegram continues working and the dashboard says so.
Only real newly detected appointments generate an email; tests use mocks.

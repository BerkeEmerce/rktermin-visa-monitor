"""Send one explicitly requested SMTP test; never check appointments or modify monitor state."""
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import os
import smtplib
import ssl
import sys

def main():
    required = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        print("Missing GitHub Actions secrets: " + ", ".join(missing))
        return 1
    try:
        port = int(os.environ.get("SMTP_PORT") or "465")
        if port not in (465, 587):
            print("SMTP_PORT must be 465 or 587.")
            return 1
        message = EmailMessage()
        message["Subject"] = "TEST - Visa monitor email delivery"
        message["From"] = os.environ["EMAIL_FROM"]
        message["To"] = "berkeemerce@gmail.com"
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid()
        stamp = datetime.now(timezone.utc).isoformat()
        run_id = os.environ.get("GITHUB_RUN_ID", "local")
        message.set_content(
            "This is the test email you requested for the North Nicosia visa monitor.\n\n"
            "This is NOT an appointment availability alert.\n"
            "Your saved SMTP settings were used to send this message.\n"
            f"Test time (UTC): {stamp}\nGitHub Actions run: {run_id}\n\n"
            "Normal email alerts are sent only when new appointments are detected.\n"
        )
        context = ssl.create_default_context()
        connection = (smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, timeout=30, context=context)
                      if port == 465 else smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=30))
        with connection as smtp:
            if port == 587:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
            refused = smtp.send_message(message)
            if refused:
                print("SMTP server refused the test recipient.")
                return 1
        print("SUCCESS: SMTP server accepted the test email for berkeemerce@gmail.com.")
        print("Subject: TEST - Visa monitor email delivery")
        print("Inbox placement is not verified; check Inbox and Spam.")
        return 0
    except smtplib.SMTPAuthenticationError as error:
        print(f"SMTP authentication failed (code {error.smtp_code}). Check the app password and sending account.")
    except smtplib.SMTPResponseException as error:
        print(f"SMTP server rejected the request (code {error.smtp_code}).")
    except (OSError, smtplib.SMTPException, ValueError):
        print("SMTP connection or delivery failed. Check the host, TLS port, and sender settings.")
    return 1

if __name__ == "__main__":
    sys.exit(main())

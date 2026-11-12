"""Send appointment alerts using the repository's saved SMTP credentials."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(text, subject="German visa appointment available — North Nicosia"):
    settings = {key: os.environ.get(key, "").strip() for key in
                ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO")}
    if not all(settings.values()):
        raise RuntimeError("Email settings are missing")
    try:
        port = int(os.environ.get("SMTP_PORT") or "465")
        if port not in (465, 587):
            raise ValueError("Unsupported SMTP port")
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings["EMAIL_FROM"]
        message["To"] = settings["EMAIL_TO"]
        message.set_content(text)
        context = ssl.create_default_context()
        connection = (smtplib.SMTP_SSL(settings["SMTP_HOST"], port, timeout=30, context=context)
                      if port == 465 else smtplib.SMTP(settings["SMTP_HOST"], port, timeout=30))
        with connection as smtp:
            if port == 587:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings["SMTP_USERNAME"], settings["SMTP_PASSWORD"])
            if smtp.send_message(message):
                raise RuntimeError("Email recipient was refused")
    except (OSError, smtplib.SMTPException, ValueError):
        raise RuntimeError("Email delivery could not be confirmed") from None


if __name__ == "__main__":
    send_email("This is a delivery test for your North Nicosia visa monitor.\n"
               "This is NOT an appointment availability alert.\n"
               "Future appointment alerts will be sent to this address alongside Telegram alerts.",
               subject="TEST - North Nicosia visa monitor email")
    print("SMTP server accepted the labeled test email.")

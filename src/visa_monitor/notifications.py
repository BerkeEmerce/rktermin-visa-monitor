"""Appointment alerts only. Health and recovery information stays in run history."""
from datetime import date
from email.message import EmailMessage
import os
import smtplib
import ssl
import requests

class NotificationError(Exception):
    pass

class Telegram:
    def __init__(self,token,chat_id,session=None):
        self.token,self.chat_id = token,chat_id
        self.session = session or requests.Session()

    def send(self,text):
        if not self.token or not self.chat_id:
            raise NotificationError("Telegram credentials are missing")
        try:
            response = self.session.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id":self.chat_id,"text":text,"link_preview_options":{"is_disabled":True}},timeout=20)
            data = response.json()
            if response.status_code!=200 or data.get("ok") is not True or not isinstance(data.get("result"),dict) or not data["result"].get("message_id"):
                raise NotificationError("Telegram rejected delivery")
        except (requests.RequestException,ValueError,AttributeError):
            raise NotificationError("Telegram delivery could not be confirmed") from None

class Email:
    """Optional authenticated SMTP. No credentials or recipient in public logs."""
    def __init__(self,host,port,username,password,sender,recipient):
        self.host,self.port = host,port
        self.username,self.password = username,password
        self.sender,self.recipient = sender,recipient

    @classmethod
    def from_env(cls,env=None):
        source = os.environ if env is None else env
        e = dict(source)
        for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"):
            if key in e:
                e[key] = e[key].strip()
        if not e.get("SMTP_HOST"):
            return None
        required = ("SMTP_USERNAME","SMTP_PASSWORD","EMAIL_FROM")
        if not all(e.get(key) for key in required):
            raise ValueError("Email requires SMTP_USERNAME, SMTP_PASSWORD and EMAIL_FROM")
        port = int(e.get("SMTP_PORT","465"))
        if port not in (465,587):
            raise ValueError("SMTP_PORT must be 465 (TLS) or 587 (STARTTLS)")
        return cls(e["SMTP_HOST"],port,e["SMTP_USERNAME"],e["SMTP_PASSWORD"],
                   e["EMAIL_FROM"],e.get("EMAIL_TO") or "berkeemerce@gmail.com")

    def send(self,text):
        message = EmailMessage()
        message["Subject"] = "German visa appointment available — North Nicosia"
        message["From"],message["To"] = self.sender,self.recipient
        message.set_content(text)
        try:
            context = ssl.create_default_context()
            if self.port == 465:
                connection = smtplib.SMTP_SSL(self.host,self.port,timeout=20,context=context)
            else:
                connection = smtplib.SMTP(self.host,self.port,timeout=20)
            with connection as smtp:
                if self.port == 587:
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(self.username,self.password)
                refused = smtp.send_message(message)
                if refused:
                    raise NotificationError("Email recipient was not accepted")
        except (OSError,smtplib.SMTPException,ValueError):
            raise NotificationError("Email delivery could not be confirmed") from None

def alert_text(dates,result,now,config):
    rendered = ", ".join(date.fromisoformat(x).strftime("%d %B %Y") for x in dates)
    return ("GERMAN VISA APPOINTMENT AVAILABLE\n\n"
        f"Location: {config.location_name}\nCategory: {config.category}\nAvailable dates: {rendered}\n"
        f"Checked at: {now.strftime('%H:%M %Z')} ({config.timezone})\n"
        f"Check status: {result.status.value}\n\nBook here: {config.booking_url}\n"
        "The portal may require a new CAPTCHA. Availability can change before you book.")

def deliver(state,result,now,config,sender,email_sender=None):
    if config.dry_run:
        return []
    sent,errors = [],{}
    stamp = now.isoformat()
    # Each channel acknowledges independently: a failed email must not resend Telegram.
    channels = [("telegram",sender,"notified_dates","availability")]
    if email_sender is not None:
        channels.append(("email",email_sender,"email_notified_dates","email"))
    for name,channel,field,label in channels:
        new_dates = sorted(set(result.dates)-set(getattr(state,field)))
        if not new_dates:
            continue
        try:
            channel.send(alert_text(new_dates,result,now,config))
        except NotificationError:
            errors[name] = "Delivery could not be confirmed"
        else:
            setattr(state,field,sorted(set(getattr(state,field))|set(new_dates)))
            state.last_notification = stamp
            sent.append(label)
    state.delivery_errors = errors
    state.notification_error = bool(errors)
    if result.complete:
        state.recovery_pending = False
    if errors:
        raise NotificationError("Appointment delivery failed for: " + ", ".join(errors))
    return sent

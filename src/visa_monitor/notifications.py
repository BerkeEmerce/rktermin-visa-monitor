from datetime import date, datetime, timedelta
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

def deliver(state,result,now,config,sender):
    if config.dry_run:
        return []
    sent = []
    stamp = now.isoformat()
    new_dates = sorted(set(result.dates)-set(state.notified_dates))
    if new_dates:
        rendered = ", ".join(date.fromisoformat(x).strftime("%d %B %Y") for x in new_dates)
        sender.send("GERMAN VISA APPOINTMENT AVAILABLE\n\n"
            f"Location: {config.location_name}\nCategory: {config.category}\nAvailable dates: {rendered}\n"
            f"Checked at: {now.strftime('%H:%M %Z')} ({config.timezone})\n"
            f"Check status: {result.status.value}\n\nBook here: {config.booking_url}\n"
            "The portal may require a new CAPTCHA. Availability can change before you book.")
        state.notified_dates = sorted(set(state.notified_dates)|set(new_dates))
        state.last_notification = stamp
        sent.append("availability")
    if result.complete and state.recovery_pending:
        sender.send("RK-Termin monitoring recovered. Available months within the configured horizon were checked successfully.")
        state.recovery_pending = False
        state.last_notification = stamp
        sent.append("recovery")
    reference = state.last_success or state.first_run or stamp
    stale = now-datetime.fromisoformat(reference)>=timedelta(hours=config.stale_hours)
    alert_due = not state.last_operational_alert or now-datetime.fromisoformat(state.last_operational_alert)>=timedelta(hours=config.alert_hours)
    if not result.complete and alert_due and (state.failures>=config.failure_threshold or stale or state.last_error in ("PARSE_ERROR","ACCESS_BLOCKED")):
        sender.send(f"RK-Termin monitoring needs attention: {state.last_error}. "
                    f"Consecutive failures: {state.failures}. Last complete success: {state.last_success or 'never'}. "
                    "Appointment availability is UNKNOWN. Inspect the Actions log.")
        state.last_operational_alert = stamp
        state.last_notification = stamp
        sent.append("operational")
    day = now.date().isoformat()
    if config.daily_summary and state.last_summary_day!=day:
        sender.send(f"RK-Termin daily health ({day}, {config.timezone})\n"
                    f"Most recent complete success: {state.last_success or 'never'}\n"
                    f"Successful complete checks today: {state.daily_successes}\n"
                    f"Previous recorded day successes: {state.previous_day_successes}\n"
                    f"Latest status: {state.last_status}; failures: {state.failures}.\n"
                    "This summary cannot detect a stopped GitHub scheduler.")
        state.last_summary_day = day
        state.last_notification = stamp
        sent.append("summary")
    state.notification_error = False
    return sent

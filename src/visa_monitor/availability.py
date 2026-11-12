from datetime import date
from .calendar_parser import parse_calendar
from .models import CheckError, CheckResult, Status

def add_months(day,count):
    index = day.year*12+day.month-1+count
    return date(index//12,index%12+1,1)

def check_availability(client,today):
    months = [add_months(today,i) for i in range(client.config.months)]
    inspected,dates = [],set()
    boundary = None
    try:
        html,url = client.open_calendar(months[0],today)
        page = parse_calendar(html,url,months[0],today,client.config)
        for i,month in enumerate(months):
            if i:
                page = client.next_month(page,month,today)
                if page is None:
                    boundary = "Portal did not offer or advance beyond " + inspected[-1]
                    break
            inspected.append(month.strftime("%Y-%m"))
            dates.update(d.isoformat() for d in page.dates)
        return CheckResult(Status.AVAILABLE if dates else Status.UNAVAILABLE,
                           inspected,sorted(dates),reason=boundary,captcha=dict(client.metrics))
    except CheckError as exc:
        return CheckResult(Status.PARTIAL_CHECK if inspected else exc.status,
                           inspected,sorted(dates),exc.status.value,exc.reason,
                           exc.retry_after,dict(client.metrics))

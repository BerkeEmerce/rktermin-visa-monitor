import argparse
import json
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo
from .availability import check_availability
from .config import Config
from .github_state import GitHubState, StateStorageError
from .notifications import NotificationError, Telegram, deliver
from .portal_client import PortalClient
from .state import due, load_local, record, save_local, roll_day
from .models import CheckResult,Status

def execute(config,state,client,sender,now,persist):
    if state.target and state.target!=config.target:
        raise ValueError("Stored target differs from configuration; use a separate repository/state")
    if not due(state,now):
        roll_day(state,now)
        cached = CheckResult(Status(state.last_status or "NETWORK_ERROR"),months=state.months,error=state.last_error)
        try:
            deliver(state,cached,now,config,sender)
        except NotificationError:
            state.notification_error = True
        persist(state)
        print(json.dumps({"status":"SKIPPED","next_check":state.next_check,"blocked_until":state.blocked_until}))
        return 1 if state.notification_error else 0
    state.target = config.target
    result = check_availability(client,now.date())
    record(state,result,now,config)
    persist(state)
    failed = False
    try:
        deliver(state,result,now,config,sender)
    except NotificationError:
        state.notification_error = True
        failed = True
    persist(state)
    print(json.dumps(asdict(result)|{"notification_error":failed},sort_keys=True))
    return 0 if result.complete and not failed else 1

def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimental RK-Termin monitor; never books")
    parser.add_argument("command",choices=["check","diagnostic","telegram-test"])
    parser.add_argument("--state",default="state.json")
    parser.add_argument("--github-state",action="store_true")
    parser.add_argument("--initialize-state",action="store_true")
    args = parser.parse_args(argv)
    try:
        config = Config.from_env()
        now = datetime.now(ZoneInfo(config.timezone))
        sender = Telegram(config.token,config.chat_id)
        if args.command=="telegram-test":
            sender.send("RK-Termin test notification. Telegram delivery works; calendar monitoring is not yet verified.")
            print("Telegram test delivery confirmed")
            return 0
        if args.command=="diagnostic":
            result = check_availability(PortalClient(config),now.date())
            print(json.dumps(asdict(result),sort_keys=True))
            return 0 if result.complete else 1
        if args.github_state and config.dry_run:
            raise ValueError("Cloud monitoring requires DRY_RUN=false; use diagnostic for a non-persistent check")
        if not config.dry_run and (not config.token or not config.chat_id):
            raise ValueError("Configure Telegram secrets before enabling monitoring")
        store = GitHubState() if args.github_state else None
        state = store.load(args.initialize_state) if store else load_local(args.state)
        persist = store.save if store else lambda value:save_local(args.state,value)
        return execute(config,state,PortalClient(config),sender,now,persist)
    except (ValueError,StateStorageError,NotificationError) as exc:
        print(json.dumps({"status":"CONFIG_OR_DELIVERY_ERROR","reason":str(exc)}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())

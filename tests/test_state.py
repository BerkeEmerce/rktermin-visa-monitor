import base64
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock
import pytest
import responses
from visa_monitor.github_state import GitHubState,StateStorageError
from visa_monitor.main import execute,main
from visa_monitor.models import CheckResult,Status
from visa_monitor.notifications import NotificationError
from visa_monitor.state import State,due,record,load_local,save_local

API = "https://api.github.com/repos/owner/monitor"

def test_state_round_trip(tmp_path,now):
    path = tmp_path/"state.json"
    state = State(last_success=now.isoformat(),notified_dates=["2026-12-18"])
    save_local(path,state)
    assert load_local(path)==state

@pytest.mark.parametrize("text",['{}','not json','{"version":2}','{"version":1,"failures":-1}','{"version":1,"last_success":"2026-11-12T12:00:00"}','{"version":1,"notified_dates":["invalid"]}'])
def test_corrupt_state_never_resets(text):
    with pytest.raises((ValueError,TypeError)):
        State.decode(text)

def test_block_cooldown(config,now):
    state = State()
    record(state,CheckResult(Status.ACCESS_BLOCKED,error="ACCESS_BLOCKED",retry_after=172800),now,config)
    assert not due(state,now+timedelta(hours=25))
    assert due(state,now+timedelta(hours=49))

def test_network_failures_do_not_update_last_success(config,now):
    state = State(last_success=(now-timedelta(hours=1)).isoformat())
    old = state.last_success
    record(state,CheckResult(Status.NETWORK_ERROR),now,config)
    assert state.last_success==old and state.failures==1

def test_partial_never_counts_as_complete(config,now):
    state = State()
    record(state,CheckResult(Status.PARTIAL_CHECK,["2026-11"]),now,config)
    assert state.last_success is None and state.daily_successes==0

def test_day_counter_reset(config,now):
    state = State()
    record(state,CheckResult(Status.UNAVAILABLE),now,config)
    record(state,CheckResult(Status.UNAVAILABLE),now+timedelta(days=1),config)
    assert state.daily_successes==1 and state.previous_day_successes==1

@responses.activate
def test_remote_state_missing_requires_explicit_initialization():
    responses.get(API+"/contents/state.json?ref=monitor-state",status=404)
    with pytest.raises(StateStorageError,match="State missing"):
        GitHubState("owner/monitor","fixture").load()

@responses.activate
def test_remote_state_restored():
    value = State(notified_dates=["2026-12-18"])
    responses.get(API+"/contents/state.json?ref=monitor-state",json={"sha":"abc","content":base64.b64encode(value.encode().encode()).decode()})
    store = GitHubState("owner/monitor","fixture")
    assert store.load()==value and store.sha=="abc"

@responses.activate
def test_remote_state_network_error_does_not_reset():
    responses.get(API+"/contents/state.json?ref=monitor-state",status=500)
    with pytest.raises(StateStorageError):
        GitHubState("owner/monitor","fixture").load(initialize=True)

@responses.activate
def test_remote_state_cas_conflict_fails_closed():
    responses.put(API+"/contents/state.json",status=409)
    store = GitHubState("owner/monitor","fixture")
    store.sha = "original"
    with pytest.raises(StateStorageError):
        store.save(State())

@responses.activate
def test_initial_state_branch(monkeypatch):
    responses.get(API+"/contents/state.json?ref=monitor-state",status=404)
    responses.get(API+"/git/ref/heads/monitor-state",status=404)
    responses.post(API+"/git/refs",status=201,json={})
    responses.put(API+"/contents/state.json",status=201,json={"content":{"sha":"new"}})
    monkeypatch.setenv("GITHUB_SHA","a"*40)
    store = GitHubState("owner/monitor","fixture")
    state = store.load(initialize=True)
    store.save(state)
    assert store.sha=="new"

@responses.activate
def test_existing_but_missing_state_not_reinitialized():
    responses.get(API+"/contents/state.json?ref=monitor-state",status=404)
    responses.get(API+"/git/ref/heads/monitor-state",json={})
    with pytest.raises(StateStorageError,match="Existing state branch"):
        GitHubState("owner/monitor","fixture").load(initialize=True)

def test_execute_cooldown_skips_portal(config,now):
    state = State(next_check=(now+timedelta(hours=1)).isoformat())
    client = Mock()
    assert execute(config,state,client,Mock(),now,Mock())==0
    assert not client.open_calendar.called

def test_execute_persists_failed_check(monkeypatch,config,now):
    import visa_monitor.main as module
    monkeypatch.setattr(module,"check_availability",lambda *args:CheckResult(Status.NETWORK_ERROR))
    state,writes = State(),[]
    assert execute(config,state,Mock(),Mock(),now,lambda s:writes.append(s.encode()))==1
    assert len(writes)==2 and State.decode(writes[-1]).failures==1

def test_execute_notification_failure_is_saved(monkeypatch,config,now):
    import visa_monitor.main as module
    monkeypatch.setattr(module,"check_availability",lambda *args:CheckResult(Status.AVAILABLE,dates=["2026-11-18"]))
    state,writes = State(),[]
    sender = Mock(send=Mock(side_effect=NotificationError()))
    assert execute(replace(config,dry_run=False),state,Mock(),sender,now,lambda s:writes.append(s.encode()))==1
    restored = State.decode(writes[-1])
    assert restored.notification_error and restored.notified_dates==[]

def test_target_change_refused(config,now):
    with pytest.raises(ValueError,match="Stored target"):
        execute(config,State(target="other"),Mock(),Mock(),now,Mock())

def test_auto_booking_rejected(monkeypatch):
    monkeypatch.setenv("AUTO_BOOK","true")
    assert main(["diagnostic"])==2


def test_scheduler_jitter_does_not_skip_next_slot(config,now):
    state = State()
    record(state,CheckResult(Status.UNAVAILABLE),now.replace(minute=7,second=45),config)
    assert due(state,now.replace(minute=22,second=5))

def test_interval_60_throttles_checks(config,now):
    state = State()
    record(state,CheckResult(Status.UNAVAILABLE),now.replace(minute=7),replace(config,interval=60))
    assert not due(state,now.replace(minute=22))
    assert due(state,now.replace(minute=7)+timedelta(hours=1))

def test_cooldown_daily_summary_without_portal_check(config,now):
    state = State(blocked_until=(now+timedelta(hours=24)).isoformat(),last_status="ACCESS_BLOCKED",
                  last_error="ACCESS_BLOCKED",day=(now-timedelta(days=1)).date().isoformat(),daily_successes=2)
    sender,client = Mock(),Mock()
    assert execute(replace(config,dry_run=False),state,client,sender,now,Mock())==0
    assert sender.send.called and not client.open_calendar.called
    assert state.daily_successes==0 and state.previous_day_successes==2

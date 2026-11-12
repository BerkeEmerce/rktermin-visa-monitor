from pathlib import Path
import pytest
import yaml
from visa_monitor.config import Config

ROOT = Path(__file__).parents[1]

def test_schedule_and_cloud_safety():
    workflow = yaml.load((ROOT/".github/workflows/monitor.yml").read_text(),Loader=yaml.BaseLoader)
    assert workflow["on"]["schedule"][0]["cron"]=="7,22,37,52 * * * *"
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["concurrency"]["cancel-in-progress"]=="false"
    job = workflow["jobs"]["check"]
    assert job["runs-on"]=="ubuntu-24.04"
    assert int(job["timeout-minutes"])<=10
    assert "MONITOR_ENABLED" in job["if"] and "private == false" in job["if"]
    assert job["env"]["MONTHS_TO_CHECK"]=="3"
    assert "secrets.TELEGRAM_BOT_TOKEN" in job["env"]["TELEGRAM_BOT_TOKEN"]
    assert "--github-state" in str(job["steps"])

@pytest.mark.parametrize("env",[{"AUTO_BOOK":"true"},{"MAX_CAPTCHA_ATTEMPTS":"3"},{"MONTHS_TO_CHECK":"4"},{"CHECK_INTERVAL_MINUTES":"5"},{"REQUEST_DELAY_SECONDS":"0"}])
def test_invalid_configuration(env):
    with pytest.raises(ValueError):
        Config.from_env(env)

def test_expected_target_and_secrets_private():
    config = Config.from_env({"TELEGRAM_BOT_TOKEN":"TEST_SECRET","TELEGRAM_CHAT_ID":"SECRET_ID"})
    assert config.params=={"locationCode":"niko","realmId":"926","categoryId":"1860"}
    assert config.timezone=="Asia/Nicosia"
    assert "TEST_SECRET" not in repr(config) and "SECRET_ID" not in repr(config)

def test_history_and_appointment_only_notifications():
    workflow = yaml.load((ROOT/".github/workflows/monitor.yml").read_text(),Loader=yaml.BaseLoader)
    job = workflow["jobs"]["check"]
    assert job["env"]["DAILY_SUMMARY"]=="false"
    assert job["env"]["EMAIL_TO"]=="berkeemerce@gmail.com"
    assert "telegram-test" not in workflow["on"]["workflow_dispatch"]["inputs"]["mode"]["options"]
    archive = next(step for step in job["steps"] if step.get("name")=="Archive run history")
    assert "always()" in archive["if"]
    assert "tee monitor-result.jsonl" in str(job["steps"])

def test_configuration_deployment_runs_live_monitor():
    workflow = yaml.load((ROOT/".github/workflows/monitor.yml").read_text(),Loader=yaml.BaseLoader)
    assert workflow["on"]["push"]["branches"]==["main"]
    assert workflow["on"]["push"]["paths"]==[".github/workflows/monitor.yml"]

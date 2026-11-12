from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from visa_monitor.config import Config

FIXTURES = Path(__file__).parent/"fixtures"

@pytest.fixture
def config():
    return Config()

@pytest.fixture
def now():
    return datetime(2026,11,12,14,15,tzinfo=ZoneInfo("Asia/Nicosia"))

@pytest.fixture
def fixture():
    return lambda name:(FIXTURES/name).read_text(encoding="utf-8")

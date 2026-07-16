import os

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

from main import app

client = TestClient(app)


def test_healthz_public():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_widgets_requires_auth():
    r = client.get("/api/v1/widgets")
    assert r.status_code == 401


def test_widgets_with_auth():
    r = client.get("/api/v1/widgets", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 200
    data = r.json()
    assert "gate" in data
    assert "telegram_queue" in data
    assert "recent_signals" in data
    assert "defi_report" in data
    assert "tradingview" in data
    assert "system_health" in data


def test_status_with_auth():
    r = client.get("/api/v1/status", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated_user"] == "testuser"
    assert data["gate"]["state"] in {"killswitch", "armed", "disarmed"}

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

from main import app

client = TestClient(app)


def _subprocess_import(password: str) -> subprocess.CompletedProcess:
    code = (
        "import os;"
        "os.environ['AUTH_USERNAME']='u';"
        f"os.environ['AUTH_PASSWORD']={password!r};"
        "import main;"
        "main._auth_credentials.cache_clear();"
        "main._auth_credentials()"
    )
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )


def test_weak_password_rejected():
    result = _subprocess_import("short")
    assert result.returncode != 0
    assert "at least 12 characters" in result.stderr


def test_common_password_rejected():
    result = _subprocess_import("sapphirealpha")
    assert result.returncode != 0
    assert "too weak" in result.stderr


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


def test_security_headers():
    r = client.get("/healthz")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_assets_path_traversal_blocked():
    r = client.get("/assets/%2e%2e/%2e%2e/etc/passwd", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 403


def test_assets_nonexistent_returns_404():
    r = client.get("/assets/does-not-exist.js", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 404

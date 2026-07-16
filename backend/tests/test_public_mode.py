"""Public read-only mode (PUBLIC_READ_ONLY=1) — anonymous access + payload sanitization."""

import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

import main
from main import app

client = TestClient(app)

AUTH = ("testuser", "testpass-strong-99")

# Strings that must NEVER appear in an anonymous payload.
FORBIDDEN_SUBSTRINGS = [
    "ts.net",
    "tailfbdf93",
    "192.168.",
    "127.0.0.1",
    "/Users/",
    "C:\\Users",
    "desktop-hfck6u9",
    "authenticated_user",
]


@pytest.fixture
def public_mode(monkeypatch):
    # Reset the TV probe cache so the fixture's URL never leaks into other tests.
    monkeypatch.setattr(main, "_tv_probe_cache", {"ts": 0.0, "result": None})
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    # Realistic-looking sensitive state that sanitization must strip.
    monkeypatch.setenv(
        "TV_WEBHOOK_URL", "http://desktop-hfck6u9-2.tailfbdf93.ts.net:9090"
    )
    monkeypatch.setenv(
        "DASHBOARD_SKIN_BOOK",
        json.dumps(
            {
                "updated": 1783914740,
                "deployed_usd": 123.45,
                "n_open": 2,
                "skin_in_game": True,
                "positions": [{"symbol": "RICH"}],
                "fills": [],
                "limits": {"per_order_cap_pct": 5, "max_daily_usd": 100},
            }
        ),
    )
    monkeypatch.setenv(
        "DASHBOARD_SIGNALS_JSON",
        json.dumps(
            [{"instrument": "BTC", "side": "BUY", "venue": "on_chain", "confidence": "high"}]
        ),
    )
    monkeypatch.setenv(
        "DASHBOARD_TDR_CLIPS_JSON",
        json.dumps(
            [{"id": "ep-1", "title": "Episode one", "source": "tdr_pro", "path": "/Users/aribs/Knowledge/clip.md"}]
        ),
    )
    yield


def test_public_mode_off_widgets_requires_auth(monkeypatch):
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    assert client.get("/api/v1/widgets").status_code == 401
    assert client.get("/api/v1/status").status_code == 401
    assert client.get("/").status_code == 401


def test_anonymous_widgets_sanitized(public_mode):
    r = client.get("/api/v1/widgets")
    assert r.status_code == 200
    data = r.json()
    body = json.dumps(data)

    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in body, f"forbidden string {needle!r} leaked into public payload"

    assert data["public_view"] is True
    # Gate: state booleans kept, caps/wallet dropped.
    assert data["gate"]["state"] in {"killswitch", "armed", "disarmed"}
    assert "cap_usd" not in data["gate"]
    assert "wallet_address" not in data["gate"]
    # Wallet: masked address + funded boolean, no exact capital, no limits.
    assert data["wallet"]["funded"] is True
    assert data["wallet"]["deployed_usd_approx"] % 10 == 0
    assert "deployed_usd" not in data["wallet"]
    assert "limits" not in data["wallet"]
    # Telegram: count only, no proposal bodies.
    assert isinstance(data["telegram_queue"]["pending"], int)
    assert data["telegram_queue"]["proposals"] == []
    # Signals: symbol/side/time only — no confidence/venue (strategy internals).
    for sig in data["recent_signals"]:
        assert set(sig) == {"id", "instrument", "side", "timestamp"}
    # TDR clips: titles only, no file paths.
    for clip in data["defi_report"]["clips"]:
        assert clip["path"] == ""
    assert data["defi_report"]["clips"][0]["title"] == "Episode one"
    # TradingView: no endpoint URL, no log tail.
    assert "endpoint" not in data["tradingview"]
    assert "recent_log" not in data["tradingview"]
    # Business health: name+status only, no probe details/URLs.
    for svc in data["business_health"]["services"]:
        assert set(svc) == {"name", "status"}
    assert "rendered_at" in data


def test_anonymous_status_sanitized(public_mode):
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    data = r.json()
    body = json.dumps(data)
    for needle in FORBIDDEN_SUBSTRINGS:
        assert needle not in body
    assert data["public_view"] is True
    assert "authenticated_user" not in data
    assert "limits" not in data["wallet"]


def test_authed_widgets_full_payload(public_mode):
    r = client.get("/api/v1/widgets", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "public_view" not in data
    assert data["wallet"]["deployed_usd"] == 123.45
    assert data["wallet"]["limits"] == {"per_order_cap_pct": 5, "max_daily_usd": 100}
    assert data["gate"]["cap_usd"] == 25
    assert "endpoint" in data["tradingview"]
    assert data["recent_signals"][0]["confidence"] == "high"
    assert data["recent_signals"][0]["venue"] == "on_chain"


def test_authed_status_full_payload(public_mode):
    r = client.get("/api/v1/status", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["authenticated_user"] == "testuser"
    assert "limits" in data["wallet"]


def test_bad_credentials_rejected_even_in_public_mode(public_mode):
    """Presented-but-wrong creds must 401, never silently fall back to public."""
    r = client.get("/api/v1/widgets", auth=("testuser", "wrong-password-xx"))
    assert r.status_code == 401


def test_vault_rag_map_always_requires_auth(public_mode):
    """The Knowledge-vault map is personal — pinned to full auth forever."""
    assert client.get("/vault/rag-map").status_code == 401


def test_vault_rag_map_authed_still_works(public_mode, tmp_path, monkeypatch):
    (tmp_path / "rag-map.html").write_text("<canvas id='map'></canvas>")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)
    r = client.get("/vault/rag-map", auth=AUTH)
    assert r.status_code == 200


def test_anonymous_frontend_and_assets(public_mode, tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html><body>sapphire</body></html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok')")
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "sapphire" in r.text
    assert client.get("/assets/app.js").status_code == 200


def test_anonymous_tradingview_alerts_counts_only(public_mode):
    r = client.get("/api/v1/tradingview/alerts")
    assert r.status_code == 200
    data = r.json()
    assert data["alerts"] == []
    assert data["public_view"] is True


def test_mutating_methods_still_denied(public_mode):
    """No anonymous non-GET access: POST is either 401 (auth) or 405 (no such route)."""
    for path in ("/api/v1/widgets", "/api/v1/status", "/"):
        r = client.post(path)
        assert r.status_code in (401, 405)
        assert r.status_code != 200


def test_public_rate_limit_tightened(public_mode):
    assert main._api_rate_limit() == "20/minute"


def test_rate_limit_normal_when_private(monkeypatch):
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    assert main._api_rate_limit() == "60/minute"


def test_round_usd():
    assert main._round_usd(123.45) == 120
    assert main._round_usd(0) == 0
    assert main._round_usd(4.9) == 0
    assert main._round_usd(5.1) == 10

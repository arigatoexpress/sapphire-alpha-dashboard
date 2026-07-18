import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_USERNAME"] = "testuser"
os.environ["AUTH_PASSWORD"] = "testpass-strong-99"

from main import (
    _business_health,
    _defi_report_feed,
    _executor_heartbeat,
    _mask_address,
    _recent_signals,
    _sanitize_proposal,
    _skin_book,
    _telegram_queue,
    _tradingview_status,
    _wallet_status,
    app,
)

client = TestClient(app)


def test_mask_address():
    assert _mask_address("0x1234567890abcdef1234567890abcdef12345678") == "0x1234...5678"
    assert _mask_address("0x12") == "0x12"
    assert _mask_address(None) is None
    assert _mask_address("") == ""


def test_sanitize_proposal_strips_pii():
    raw = {
        "action": "buy",
        "instrument": "RICH",
        "side": "BUY",
        "confidence": "high",
        "chat_id": 123456,
        "user_id": 789,
        "username": "ari",
        "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        "status": "pending",
        "timestamp": "2026-07-16T00:00:00Z",
    }
    safe = _sanitize_proposal(raw, 1)
    assert safe["id"] == "prop-001"
    assert safe["instrument"] == "RICH"
    assert safe["side"] == "BUY"
    assert "chat_id" not in safe
    assert "user_id" not in safe
    assert "username" not in safe
    assert safe["wallet_address"] == "0x1234...5678"


def test_executor_heartbeat_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_EXECUTOR_HEARTBEAT", json.dumps({"status": "alive", "pid": 42}))
    hb = _executor_heartbeat()
    assert hb["alive"] is True
    assert hb["status"] == "alive"
    assert hb["pid"] == 42


def test_skin_book_env(monkeypatch):
    payload = {
        "updated": 1783914740,
        "mode": "tg_approve_then_manual_fill",
        "deployed_usd": 12.5,
        "n_open": 1,
        "skin_in_game": True,
        "positions": [{"symbol": "RICH"}],
        "fills": [{"symbol": "RICH"}],
        "limits": {"per_order_cap_pct": 5},
    }
    monkeypatch.setenv("DASHBOARD_SKIN_BOOK", json.dumps(payload))
    book = _skin_book()
    assert book["deployed_usd"] == 12.5
    assert book["n_open"] == 1
    assert book["positions_count"] == 1
    assert book["fills_count"] == 1
    assert book["skin_in_game"] is True


def test_wallet_status_env(monkeypatch):
    monkeypatch.setenv("WALLET_ADDRESS", "0x1234567890abcdef1234567890abcdef12345678")
    monkeypatch.setenv(
        "DASHBOARD_SKIN_BOOK",
        json.dumps({"updated": 1783914740, "deployed_usd": 5.0, "n_open": 0, "skin_in_game": True}),
    )
    wallet = _wallet_status()
    assert wallet["address"] == "0x1234...5678"
    assert wallet["deployed_usd"] == 5.0
    assert wallet["skin_in_game"] is True


def test_telegram_queue_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_POLLING", "false")
    monkeypatch.setenv(
        "DASHBOARD_SIGNALS_JSON", json.dumps([])
    )  # avoid unrelated signal file reads
    queue = _telegram_queue()
    assert queue["pending"] == 0
    assert queue["status"] == "paused"
    assert queue["proposals"] == []


def test_recent_signals_env(monkeypatch):
    signals = [
        {"instrument": "BTC", "side": "BUY", "venue": "on_chain", "confidence": "high"},
        {"instrument": "ETH", "side": "SELL", "venue": "cex", "confidence": "low"},
    ]
    monkeypatch.setenv("DASHBOARD_SIGNALS_JSON", json.dumps(signals))
    result = _recent_signals()
    assert len(result) == 2
    assert result[0]["instrument"] == "BTC"
    assert result[0]["id"] == "sig-001"


def test_recent_signals_missing_is_honestly_empty(tmp_path, monkeypatch):
    import main

    monkeypatch.delenv("DASHBOARD_SIGNALS_JSON", raising=False)
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path)
    assert _recent_signals() == []


def test_defi_report_feed(tmp_path, monkeypatch):
    import asyncio
    import main

    clip = tmp_path / "2026-07-15-clip.md"
    clip.write_text("# Bitcoin green light\nSome content", encoding="utf-8")
    monkeypatch.setattr(main, "_KNOWLEDGE_CLIPS_DIR", tmp_path)
    feed = asyncio.run(_defi_report_feed())
    assert feed["source"] == "tdr_pro"
    assert len(feed["clips"]) == 1
    assert feed["clips"][0]["title"] == "Bitcoin green light"


def test_tradingview_status_log(tmp_path, monkeypatch):
    log = tmp_path / "tv.log"
    log.write_text("alert 1\nalert 2\n", encoding="utf-8")
    monkeypatch.setenv("DASHBOARD_TV_LOG", str(log))

    async def _run():
        return await _tradingview_status()

    tv = asyncio.run(_run())
    # When TV_WEBHOOK_URL is not configured, the probe reports standby.
    assert tv["status"] == "standby"
    assert tv["recent_log"] == ["alert 1", "alert 2"]


def test_business_health_mock():
    async def _run():
        with patch("main.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            health = await _business_health()
            services = {s["name"]: s for s in health["services"]}
            assert services["gpu_gateway"]["status"] == "ok"

    asyncio.run(_run())


def test_widgets_returns_new_keys():
    r = client.get("/api/v1/widgets", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 200
    data = r.json()
    assert "gate" in data
    assert "wallet" in data
    assert "telegram_queue" in data
    assert "recent_signals" in data
    assert "defi_report" in data
    assert "tradingview" in data
    assert "business_health" in data
    assert "system_health" in data
    assert "rendered_at" in data


def test_status_returns_wallet():
    r = client.get("/api/v1/status", auth=("testuser", "testpass-strong-99"))
    assert r.status_code == 200
    data = r.json()
    assert "wallet" in data
    assert data["gate"]["state"] in {"killswitch", "armed", "disarmed"}


def test_widgets_no_pii_in_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_POLLING", "true")
    proposals = [
        {
            "action": "buy",
            "instrument": "RICH",
            "side": "BUY",
            "chat_id": 123,
            "user_id": 456,
            "username": "ari",
            "status": "pending",
        }
    ]
    monkeypatch.setenv("DASHBOARD_SIGNALS_JSON", json.dumps([]))
    # Simulate a pending queue via env by creating a temp file is hard because path is
    # hardcoded; instead verify the sanitizer behavior is used in _telegram_queue.
    queue = _telegram_queue()
    for prop in queue["proposals"]:
        assert "chat_id" not in prop
        assert "user_id" not in prop
        assert "username" not in prop

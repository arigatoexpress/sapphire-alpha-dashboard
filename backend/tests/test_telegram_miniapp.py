"""Tests for the Telegram Mini App surface: initData auth + read-only projections."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import main
import telegram_miniapp as tma

BOT_TOKEN = "1234567890:TEST-token-not-real"
USER_ID = 6826484357


def make_init_data(
    user_id: int = USER_ID,
    auth_date: int | None = None,
    bot_token: str = BOT_TOKEN,
    tamper: bool = False,
) -> str:
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAtestquery",
        "user": json.dumps({"id": user_id, "first_name": "Ari", "username": "arigatoexpress"}),
    }
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if tamper:
        fields["user"] = json.dumps({"id": user_id + 1, "first_name": "Eve"})
    return urlencode(fields)


# --- validate_init_data ----------------------------------------------------


def test_valid_init_data_returns_user():
    user = tma.validate_init_data(make_init_data(), BOT_TOKEN)
    assert user.id == USER_ID
    assert user.first_name == "Ari"


def test_tampered_init_data_rejected():
    with pytest.raises(tma.InitDataError):
        tma.validate_init_data(make_init_data(tamper=True), BOT_TOKEN)


def test_wrong_token_rejected():
    with pytest.raises(tma.InitDataError):
        tma.validate_init_data(make_init_data(bot_token="999:other"), BOT_TOKEN)


def test_stale_auth_date_rejected():
    stale = make_init_data(auth_date=int(time.time()) - 90000)
    with pytest.raises(tma.InitDataError, match="expired"):
        tma.validate_init_data(stale, BOT_TOKEN)


def test_missing_hash_and_empty_rejected():
    with pytest.raises(tma.InitDataError):
        tma.validate_init_data("auth_date=1", BOT_TOKEN)
    with pytest.raises(tma.InitDataError):
        tma.validate_init_data("", BOT_TOKEN)


def test_no_bot_token_configured_rejected():
    with pytest.raises(tma.InitDataError, match="not configured"):
        tma.validate_init_data(make_init_data(), "")


# --- allowlist / header auth ----------------------------------------------


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("TG_MINIAPP_ALLOWED_IDS", str(USER_ID))
    return monkeypatch


def test_header_auth_ok(env):
    user = tma.authenticate_header(f"tma {make_init_data()}")
    assert user.id == USER_ID


def test_header_auth_rejects_wrong_scheme_and_disallowed_user(env):
    with pytest.raises(tma.InitDataError):
        tma.authenticate_header(f"Bearer {make_init_data()}")
    with pytest.raises(tma.InitDataError, match="not allowed"):
        tma.authenticate_header(f"tma {make_init_data(user_id=42)}")


def test_empty_allowlist_denies_everyone(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.delenv("TG_MINIAPP_ALLOWED_IDS", raising=False)
    with pytest.raises(tma.InitDataError, match="not allowed"):
        tma.authenticate_header(f"tma {make_init_data()}")


# --- projections -----------------------------------------------------------


def test_sanitize_decision_strips_pii_and_tags_chain():
    row = {
        "id": "d1",
        "action": "buy",
        "symbol": "MOSS",
        "decision": "approved",
        "chat_id": 12345,
        "user_id": 678,
        "api_token": "secret-thing",
        "ts": "2026-07-17T00:00:00Z",
    }
    out = tma.sanitize_decision(row, 1)
    dumped = json.dumps(out)
    assert "12345" not in dumped and "678" not in dumped and "secret-thing" not in dumped
    assert out["instrument"] == "MOSS"
    assert out["decision"] == "approved"
    assert out["chain"] == "rh-chain" and out["chain_id"] == 4663


def test_sanitize_decision_respects_chain_id():
    out = tma.sanitize_decision({"chain_id": 4326, "action": "snipe"}, 2)
    assert out["chain"] == "megaeth"
    assert tma.tag_chain({}, 999)["chain"] == "chain-999"


# --- HTTP endpoints --------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main.app, raise_server_exceptions=False)


def test_summary_requires_auth(env, client):
    assert client.get("/api/tg/summary").status_code == 401
    assert (
        client.get("/api/tg/summary", headers={"Authorization": "tma bogus"}).status_code == 401
    )


def test_summary_503_when_unconfigured(monkeypatch, client):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN_FILE", raising=False)
    assert client.get("/api/tg/summary", headers={"Authorization": "tma x"}).status_code == 503


def test_summary_ok_and_sanitized(env, client):
    resp = client.get(
        "/api/tg/summary", headers={"Authorization": f"tma {make_init_data()}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain"]["chain"] == "rh-chain"
    assert set(body) >= {"desk", "wallet", "queue", "signals", "fleet"}
    # No raw chat/user ids or secrets anywhere in the payload.
    dumped = json.dumps(body).lower()
    assert "chat_id" not in dumped
    assert "bot_token" not in dumped


def test_decisions_read_only(env, client):
    resp = client.get(
        "/api/tg/decisions", headers={"Authorization": f"tma {make_init_data()}"}
    )
    assert resp.status_code == 200
    assert "decisions" in resp.json()
    # There must be NO mutating decision endpoint — approvals stay on the bot rail.
    assert client.post(
        "/api/tg/decisions", headers={"Authorization": f"tma {make_init_data()}"}
    ).status_code == 405
    for path in ("/api/tg/approve", "/api/tg/decide", "/api/tg/arm"):
        r = client.post(path, headers={"Authorization": f"tma {make_init_data()}"})
        assert r.status_code in (404, 405)


def test_miniapp_page_public(client):
    resp = client.get("/miniapp")
    assert resp.status_code == 200
    assert "telegram-web-app.js" in resp.text

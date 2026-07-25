"""Transparency pane — explanation-ledger projections + endpoint split."""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_USERNAME", "testuser")
os.environ.setdefault("AUTH_PASSWORD", "testpass-strong-99")

import transparency
from main import app

client = TestClient(app)
AUTH = (os.environ["AUTH_USERNAME"], os.environ["AUTH_PASSWORD"])


def _rec(pid="0717-eq", kind="auto_execution", **over):
    rec = {
        "schema": 1, "kind": kind, "id": pid, "ts": 1_752_000_000.0,
        "mode": "free_reign",
        "lane": "systematic",
        "signal": {"source": "equity", "features": ["momentum confirmed"]},
        "strategy": {"track": "equity", "venue": "brokerage"},
        "verification": {"verified": True, "note": "deskos-verified",
                         "checks": {"sharpe": True}, "generated_ts": 1_751_000_000.0},
        "thesis": "momentum confirmed; vol contained",
        "action": "BUY", "instrument": "NVDA:US", "size_usd": 8.0,
        "risk_bounds": {"per_trade_cap_usd": 10, "daily_cap_usd": 40},
        "outcome": None,
        "chat_id": 424242,  # hostile extra field — must never project
    }
    rec.update(over)
    return rec


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / transparency.LEDGER_NAME
    lines = [
        _rec("a"),
        _rec("b", kind="outcome", verification={},
             outcome={"pnl_usd": 1.5, "summary": "tp"}),
        {"schema": 99, "garbage": True},  # wrong schema — skipped
    ]
    path.write_text("\n".join(json.dumps(r) for r in lines) + "\nnot json\n")
    monkeypatch.setenv("DASHBOARD_EXPLANATIONS_PATH", str(path))
    return path


def test_read_ledger_skips_garbage(ledger):
    rows = transparency.read_ledger(ledger)
    assert [r["id"] for r in rows] == ["a", "b"]


def test_read_ledger_missing_file_is_empty(tmp_path):
    assert transparency.read_ledger(tmp_path / "nope.jsonl") == []


def test_usd_bands():
    assert transparency.usd_band(3) == "<$5"
    assert transparency.usd_band(8) == "$5–10"
    assert transparency.usd_band(500) == ">$100"
    assert transparency.usd_band(None) == "unknown"


def test_operator_record_is_whitelist():
    op = transparency.operator_record(_rec())
    assert op["size_usd"] == 8.0                # full detail
    assert op["verification"]["checks"] == {"sharpe": True}
    assert "chat_id" not in op                  # hostile extras dropped


def test_public_record_banded_and_hashed():
    pub = transparency.public_record(_rec())
    s = json.dumps(pub)
    assert "424242" not in s and "0717-eq" not in s
    assert pub["size_band"] == "$5–10" and "8.0" not in s
    assert pub["instrument"] == "NVDA"
    assert pub["verified"] is True and pub["public_view"] is True


def test_public_outcome_banded():
    pub = transparency.public_record(
        _rec(kind="outcome", outcome={"pnl_usd": -3.0}))
    assert pub["outcome_band"] == "<$5" and pub["outcome_sign"] == "-"


def test_snapshot_counts(ledger):
    snap = transparency.snapshot(ledger, public=False)
    assert snap["counts"] == {"total": 2, "auto_executions": 1,
                              "verified": 1, "outcomes": 1,
                              "lanes": {"systematic": 2}}


def test_lane_projects_to_both_views():
    rec = _rec(lane="thesis")
    assert transparency.operator_record(rec)["lane"] == "thesis"
    assert transparency.public_record(rec)["lane"] == "thesis"


def test_endpoint_operator_full_detail(ledger):
    r = client.get("/api/v1/transparency", auth=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["total"] == 2
    assert body["records"][0]["size_usd"] == 8.0
    assert "public_view" not in body


def test_endpoint_public_sanitized(ledger, monkeypatch):
    monkeypatch.setenv("PUBLIC_READ_ONLY", "1")
    r = client.get("/api/v1/transparency")
    assert r.status_code == 200
    body = r.json()
    assert body["public_view"] is True
    s = json.dumps(body)
    assert "424242" not in s and "size_usd" not in s
    assert body["records"][0]["size_band"] == "$5–10"


def test_endpoint_is_anonymous_and_still_sanitized_without_the_env_flag(ledger, monkeypatch):
    """Anonymous readers get the banded ledger whether or not PUBLIC_READ_ONLY is set."""
    monkeypatch.delenv("PUBLIC_READ_ONLY", raising=False)
    r = client.get("/api/v1/transparency")
    assert r.status_code == 200
    body = r.json()
    assert body["public_view"] is True
    assert "size_usd" not in json.dumps(body)

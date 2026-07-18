"""Golden privacy and fidelity tests for the home-mesh projector."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from live_telemetry import validate_snapshot
from telemetry.collector import Sources, build_snapshot, signed_headers


NOW = time.time() - 30


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_projector_is_schema_valid_real_and_strips_raw_identifiers(tmp_path):
    sources = Sources(
        rh_health=_write(tmp_path / "health.json", {"generated_ts": NOW - 4, "overall": "healthy", "agents": [{"name": "secret_process", "label": "Orderflow", "status": "healthy", "issues": [], "state_files": [{"path": "/Users/private"}]}]}),
        rh_feed=_write(tmp_path / "feed.json", {"updated": NOW - 2, "msgs_per_min": 88, "endpoint": "http://192.0.2.1"}),
        memes=_write(tmp_path / "memes.json", {"updated": NOW - 1, "tape": [{"wallet": "0x" + "a" * 40}]}),
        paper=_write(tmp_path / "paper.json", {"updated": NOW - 3, "balance": 999999, "day_halted": False}),
        gpu=_write(tmp_path / "gpu.json", {"last_check": datetime.fromtimestamp(NOW - 3, UTC).strftime("%Y-%m-%d %H:%M:%S"), "status": "up", "services": {"ollama": 1, "worker": 1}, "hostname": "private-host"}),
        desk_cycle=_write(tmp_path / "desk.json", {"finished_at": datetime.fromtimestamp(NOW - 3, UTC).isoformat(), "status": "ok", "totals": {"inserted": 50}, "source_health": [{"error": "secret"}]}),
    )
    snapshot = validate_snapshot(build_snapshot(sources, now=NOW, link_latencies={"orchestration:gpu-compute": 7.25}))
    encoded = json.dumps(snapshot).lower()
    for forbidden in ("/users/", "192.0.2", "private-host", "secret_process", "0x" + "a" * 40, "balance", "endpoint"):
        assert forbidden not in encoded
    assert snapshot["markets"]["events_per_min"] == 88
    assert snapshot["markets"]["execution"] == "off"
    assert snapshot["agents"][0]["role"] == "Orderflow"
    assert snapshot["links"][3]["event_rate"] == 88
    assert snapshot["links"][3]["latency_ms"] is None
    assert snapshot["links"][1]["latency_ms"] == 7.25


def test_missing_sources_are_honestly_offline(tmp_path):
    missing = tmp_path / "missing.json"
    snapshot = validate_snapshot(build_snapshot(Sources(missing, missing, missing, missing, missing, missing), now=NOW))
    assert snapshot["markets"]["status"] == "offline"
    assert snapshot["agents"] == []
    assert snapshot["summary"]["state"] == "degraded"
    assert all(node["status"] != "healthy" for node in snapshot["nodes"] if node["id"] != "public-edge")


def test_signature_headers_match_server_contract():
    import hashlib
    import hmac

    body = b'{"version":1}'
    headers = signed_headers(body, "x" * 32, timestamp=1234, nonce="nonce-0000000001")
    expected = hmac.new(b"x" * 32, b"1234.nonce-0000000001." + body, hashlib.sha256).hexdigest()
    assert headers["X-Sapphire-Signature"] == expected

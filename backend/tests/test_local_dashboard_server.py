from datetime import UTC, datetime

import local_dashboard_server


def test_offline_fallback_uses_the_current_single_view_contract(monkeypatch):
    observed_at = datetime.now(UTC).isoformat()
    raw = {"raw": True}
    validated = {
        "version": 1,
        "observed_at": observed_at,
        "sequence": 7,
        "summary": {},
        "nodes": [],
        "links": [],
        "agents": [],
        "markets": {},
        "events": [],
        "desk": {},
    }
    monkeypatch.setattr(local_dashboard_server.Sources, "defaults", lambda: object())
    monkeypatch.setattr(local_dashboard_server, "configured_latencies", lambda: {})
    monkeypatch.setattr(
        local_dashboard_server,
        "build_snapshot",
        lambda _sources, *, link_latencies: raw,
    )
    monkeypatch.setattr(
        local_dashboard_server,
        "validate_snapshot",
        lambda candidate: validated if candidate is raw else None,
    )

    snapshot = local_dashboard_server._build_live_snapshot()

    assert snapshot["status"] == "live"
    assert snapshot["freshness_s"] >= 0
    assert snapshot["received_at"] == observed_at
    assert snapshot["served_at"]

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


def test_offline_fallback_covers_the_dashboard_watchboard_contract():
    widgets = local_dashboard_server._empty_widgets()

    assert widgets["gate"] == {
        "state": "killswitch",
        "label": "Local fallback stopped",
        "armed": False,
        "killswitch": True,
        "mode": "offline",
        "executor_alive": False,
        "updated_at": widgets["rendered_at"],
    }
    assert widgets["recent_signals"] == []
    assert widgets["research"]["clips"] == []
    assert widgets["research"]["live"] is False
    assert widgets["research"]["policy"] == {
        "research_role": "evidence_not_authority",
        "single_input_cap": 0.25,
        "minimum_independent_checks": 2,
        "can_set_conviction": False,
        "can_authorize_execution": False,
    }
    assert widgets["system_health"]["telegram"] == "not_observed"
    assert widgets["tradingview"]["status"] == "not_observed"


def test_offline_fallback_exposes_the_same_fail_closed_build_contract():
    identity = local_dashboard_server._runtime_build_identity()

    assert identity["schema"] == 1
    assert set(identity["surfaces"]) == {"operator", "public"}
    assert isinstance(identity["complete"], bool)

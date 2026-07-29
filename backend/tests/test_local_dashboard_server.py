import json
from datetime import UTC, datetime, timedelta

import local_dashboard_server
from tests.test_live_telemetry import _sample


def test_offline_fallback_uses_the_current_single_view_contract(tmp_path):
    observed = datetime.now(UTC) - timedelta(seconds=10)
    candidate = tmp_path / "live-snapshot.json"
    candidate.write_text(
        json.dumps(_sample(observed_at=observed.isoformat(), sequence=7)),
        encoding="utf-8",
    )
    candidate.chmod(0o600)

    snapshot = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=datetime.now(UTC).timestamp(),
    )

    assert snapshot["status"] == "live"
    assert snapshot["freshness_s"] >= 0
    assert snapshot["received_at"] == observed.isoformat()
    assert snapshot["served_at"]


def test_offline_fallback_covers_the_dashboard_watchboard_contract():
    widgets = local_dashboard_server._empty_widgets()

    assert widgets["gate"] == {
        "state": "unavailable",
        "label": "Pause state unavailable",
        "armed": None,
        "killswitch": None,
        "pause_state": "unknown",
        "mode": "unavailable",
        "executor_alive": None,
        "updated_at": None,
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
    assert "telegram" not in widgets["system_health"]
    assert widgets["tradingview"]["status"] == "not_observed"


def test_offline_fallback_exposes_the_same_fail_closed_build_contract():
    identity = local_dashboard_server._runtime_build_identity()

    assert identity["schema"] == 1
    assert set(identity["surfaces"]) == {"operator", "public"}
    assert isinstance(identity["complete"], bool)

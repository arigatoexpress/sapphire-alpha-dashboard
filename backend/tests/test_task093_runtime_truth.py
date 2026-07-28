"""Task 093 goldens: persisted freshness, pause truth, and retired controls.

These tests are intentionally source-only.  They instantiate in-memory stores
and temporary files; no network, provider, message, broker, wallet, order, or
trade adapter is reachable from this module.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import live_telemetry
import main
import moss_telemetry
import owner_approval
from live_telemetry import (
    LiveTelemetryStore,
    MemoryTelemetryPersistence,
    TelemetryValidationError,
    validate_snapshot,
)
from tests.test_live_telemetry import _sample


NOW = datetime(2026, 7, 28, 18, 0, tzinfo=UTC)
TASK063_MERGED = "4205e79ac53e56b03949bf266f2a3b074a651d71"
TASK065_REVIEWED = "2d76f2a3254e5d21ca917a01f945ab1b64912aa0"
TASK065_MERGED = "f19270df630ef0cb67d439e00e07e70121dae4de"
TASK065_RESULT_SHA256 = (
    "5fba3c1802fa75ea49801fedb07f4a48cdeaefbe7ef8cd776621f6b8e5b5e916"
)
TASK065_REVIEW_SHA256 = (
    "49367a90974b4c4605aa2d2c5e004c7cec9eb0841e73062d16f8bf14f2277cfc"
)


def _stored_sample(*, observed_at: datetime = NOW) -> dict:
    sample = _sample(observed_at=observed_at.isoformat(), sequence=93)
    sample["markets"]["decision_gate"] = "manual"
    sample["desk"]["updated_at"] = observed_at.isoformat()
    sample["desk"]["autonomy"] = {
        "desired": "on",
        "active": True,
        "new_entries": "available",
        "reason": "source reported active",
    }
    sample["desk"]["safety_floor"] = {
        "gate_valid": True,
        "pause_clear": True,
        "ledger": "reconciled",
        "bounded_policy": True,
    }
    return validate_snapshot(sample)


def _store(snapshot: dict, *, received_at: datetime = NOW) -> LiveTelemetryStore:
    persistence = MemoryTelemetryPersistence()
    persistence.accept(
        snapshot,
        nonce="task093-persisted",
        received_at=received_at.timestamp(),
    )
    return LiveTelemetryStore(persistence)


def test_stale_parent_cannot_leave_fresh_looking_nested_runtime_truth() -> None:
    store = _store(_stored_sample())

    result = store.get(
        now=(NOW + timedelta(minutes=10)).timestamp(),
        stale_after_seconds=180,
    )

    assert result["status"] == "stale"
    assert result["observed_at"] == NOW.isoformat()
    assert result["markets"]["status"] == "stale"
    assert result["markets"]["feed_age_s"] == pytest.approx(604.2)
    assert result["markets"]["decision_gate"] == "unknown"
    assert result["markets"]["execution"] == "unknown"
    assert result["desk"]["execution"] == "unknown"
    assert result["desk"]["autonomy"]["active"] is False
    assert result["desk"]["safety_floor"]["pause_clear"] is None


def test_nested_desk_and_agent_truth_expires_even_while_parent_is_current() -> None:
    snapshot = _stored_sample()
    old = (NOW - timedelta(minutes=15)).isoformat()
    snapshot["desk"]["updated_at"] = old
    snapshot["agents"][0]["updated_at"] = old
    store = _store(snapshot)

    result = store.get(now=(NOW + timedelta(seconds=30)).timestamp())

    assert result["status"] == "live"
    assert result["desk"]["updated_at"] == old
    assert result["desk"]["execution"] == "unknown"
    assert result["desk"]["autonomy"]["active"] is False
    assert result["desk"]["safety_floor"]["pause_clear"] is None
    assert result["agents"][0]["state"] == "offline"
    assert result["agents"][0]["verification"] == "pending"


def test_repeated_reads_age_persisted_truth_without_retimestamping_it() -> None:
    store = _store(_stored_sample())

    first = store.get(now=(NOW + timedelta(seconds=10)).timestamp())
    second = store.get(now=(NOW + timedelta(seconds=40)).timestamp())

    assert first["observed_at"] == second["observed_at"] == NOW.isoformat()
    assert (
        first["desk"]["updated_at"] == second["desk"]["updated_at"] == NOW.isoformat()
    )
    assert first["received_at"] == second["received_at"]
    assert second["freshness_s"] - first["freshness_s"] == 30
    assert second["markets"]["feed_age_s"] - first["markets"][
        "feed_age_s"
    ] == pytest.approx(30)
    assert first["served_at"] != second["served_at"]


def test_public_moss_projection_retains_its_persisted_observation_time() -> None:
    source = {
        "observed_at": NOW.isoformat(),
        "usdm": "188.25",
        "eth": "0.0042",
    }

    first = moss_telemetry.public_projection(
        source,
        now=(NOW + timedelta(seconds=10)).timestamp(),
    )
    second = moss_telemetry.public_projection(
        source,
        now=(NOW + timedelta(seconds=40)).timestamp(),
    )

    assert first["observed_at"] == second["observed_at"] == NOW.isoformat()


@pytest.mark.parametrize(
    ("observations", "expected"),
    [
        ([], "unknown"),
        ([{"source": "mac", "state": "clear", "observed_at": "bad"}], "unknown"),
        (
            [
                {
                    "source": "mac",
                    "state": "clear",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 1),
                },
                {
                    "source": "mac",
                    "state": "active",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 2),
                },
                {
                    "source": "rh_chain",
                    "state": "clear",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 3),
                },
            ],
            "unknown",
        ),
        (
            [
                {
                    "source": "mac",
                    "state": "active",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 1),
                },
                {
                    "source": "rh_chain",
                    "state": "clear",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 2),
                },
            ],
            "active",
        ),
    ],
)
def test_pause_truth_is_tristate_and_fail_closed(
    observations: list[dict[str, str]],
    expected: str,
) -> None:
    result = main._evaluate_pause_truth(observations, now=NOW)
    assert result["state"] == expected
    if expected == "unknown":
        assert result["clear"] is None
    elif expected == "active":
        assert result["clear"] is False


def test_only_two_fresh_explicit_clear_observations_can_clear_pause() -> None:
    fresh = [
        {
            "source": source,
            "state": "clear",
            "observed_at": NOW.isoformat(),
            "_source_identity": (1, index),
        }
        for index, source in enumerate(("mac", "rh_chain"), start=1)
    ]
    stale = [
        {
            "source": source,
            "state": "clear",
            "observed_at": (NOW - timedelta(minutes=10)).isoformat(),
            "_source_identity": (2, index),
        }
        for index, source in enumerate(("mac", "rh_chain"), start=1)
    ]

    assert main._evaluate_pause_truth(fresh, now=NOW)["state"] == "clear"
    assert main._evaluate_pause_truth(stale, now=NOW)["state"] == "unknown"


def test_absent_unreadable_and_malformed_pause_files_never_mean_clear(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"
    unreadable = tmp_path / "directory-not-a-sentinel"
    unreadable.mkdir()
    malformed = tmp_path / "malformed"
    malformed.write_text("{not-json", encoding="utf-8")

    assert main._pause_file_observation("mac", missing) is None
    for path in (unreadable, malformed):
        observation = main._pause_file_observation("mac", path)
        assert observation == {
            "source": "mac",
            "state": "invalid",
            "observed_at": None,
        }
        resolved = main._evaluate_pause_truth(
            [
                observation,
                {
                    "source": "rh_chain",
                    "state": "clear",
                    "observed_at": NOW.isoformat(),
                    "_source_identity": (1, 2),
                },
            ],
            now=NOW,
        )
        assert resolved["state"] == "unknown"
        assert resolved["clear"] is None


def test_missing_pause_truth_cannot_be_force_cleared_by_retired_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path / "rh-chain")
    monkeypatch.setattr(
        main,
        "_PAUSE_SENTINELS",
        {
            "mac": tmp_path / "missing-mac-pause",
            "rh_chain": tmp_path / "missing-rh-chain-pause",
        },
    )
    monkeypatch.setenv("DASHBOARD_FORCE_KILLSWITCH", "false")
    monkeypatch.setenv("DASHBOARD_ARMED", "true")
    monkeypatch.setenv("DASHBOARD_MODE", "telegram")

    gate = main._gate_status(now=NOW)

    assert gate["state"] == "unavailable"
    assert gate["armed"] is None
    assert gate["killswitch"] is None
    assert gate["pause_state"] == "unknown"
    assert gate["mode"] == "unavailable"
    assert gate["updated_at"] is None


def test_active_persisted_pause_wins_without_request_time_freshening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh = tmp_path / "rh-chain"
    rh.mkdir()
    (rh / "gate.json").write_text(
        json.dumps(
            {
                "armed": True,
                "mode": "bounded_auto",
                "updated": NOW.timestamp(),
                "pause_sources": [
                    {
                        "source": "rh_chain",
                        "state": "clear",
                        "observed_at": NOW.isoformat(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    mac_pause = tmp_path / "mac-pause"
    mac_pause.write_text(
        json.dumps({"created_at": (NOW - timedelta(days=1)).isoformat()}),
        encoding="utf-8",
    )
    rh_pause = tmp_path / "rh-chain-pause"
    rh_pause.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh)
    monkeypatch.setattr(
        main,
        "_PAUSE_SENTINELS",
        {"mac": mac_pause, "rh_chain": rh_pause},
    )

    gate = main._gate_status(now=NOW)

    assert gate["state"] == "paused"
    assert gate["killswitch"] is True
    assert gate["armed"] is False
    assert gate["pause_state"] == "active"
    assert gate["updated_at"] == NOW.isoformat()


def test_retired_telegram_control_vocabulary_is_rejected_and_unrouted() -> None:
    sample = _sample(observed_at=NOW.isoformat(), sequence=94)
    sample["markets"]["decision_gate"] = "telegram"
    with pytest.raises(TelemetryValidationError):
        validate_snapshot(sample)

    paths = {route.path for route in main.app.routes}
    assert "/miniapp" not in paths
    assert not any(path.startswith("/api/tg/") for path in paths)

    production_files = [
        Path(main.__file__),
        Path(live_telemetry.__file__),
        Path(__file__).parents[2] / "telemetry" / "collector.py",
        Path(__file__).parents[2] / "telemetry" / "win_collector.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in production_files)
    for retired in (
        "TELEGRAM_BOT_POLLING",
        "DASHBOARD_FORCE_KILLSWITCH",
        "DASHBOARD_MODE",
        "pending_queue",
        "telegram_queue",
    ):
        assert retired not in source


def test_widgets_and_readiness_report_no_retired_control_or_unproved_runtime() -> None:
    client = TestClient(main.app)

    widgets = client.get("/api/v1/widgets").json()
    readiness = client.get("/api/v1/readiness").json()

    assert "telegram_queue" not in widgets
    assert readiness == {
        "schema_version": "sapphire-runtime-readiness/v1",
        "task063": {
            "status": "SOURCE_MERGED_INERT",
            "merged_commit": TASK063_MERGED,
        },
        "task065": {
            "status": "SOURCE_MERGED_INERT",
            "reviewed_head": TASK065_REVIEWED,
            "merged_commit": TASK065_MERGED,
            "result_sha256": TASK065_RESULT_SHA256,
            "review_sha256": TASK065_REVIEW_SHA256,
            "outcome": "TWO_ATTENDANCES_REQUIRED",
            "one_attendance": "ONE_ATTENDANCE_UNAVAILABLE",
            "production_execution": "PRODUCTION_EXECUTION_UNAVAILABLE",
        },
        "credential_enrollment": "UNAVAILABLE",
        "broker_reconciliation": "UNAVAILABLE",
        "runtime_installation": "UNAVAILABLE",
        "production_execution": "UNAVAILABLE",
    }
    assert owner_approval.DEPENDENCY_PINS["task063_merged_commit"] == TASK063_MERGED
    assert (
        owner_approval.DEPENDENCY_PINS["task065_status"]
        == "SOURCE_MERGED_INERT"
    )
    assert owner_approval.DEPENDENCY_PINS["production_execution_available"] == 0

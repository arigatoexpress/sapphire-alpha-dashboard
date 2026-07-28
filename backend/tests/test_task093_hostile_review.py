"""Hostile Task 093 R1 review regressions.

These source-only tests reproduce the sealed exact-tree review without
reaching a provider, service, message transport, broker, wallet, order, or
trade adapter.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import local_dashboard_server
import main
from live_telemetry import (
    LiveTelemetryStore,
    MemoryTelemetryPersistence,
    validate_snapshot,
)
from tests.test_live_telemetry import _sample


NOW = datetime(2026, 7, 28, 23, 30, tzinfo=UTC)


def _store(snapshot: dict, *, received_at: float) -> LiveTelemetryStore:
    persistence = MemoryTelemetryPersistence()
    persistence.accept(snapshot, nonce="task093-hostile-r1", received_at=received_at)
    return LiveTelemetryStore(persistence)


def test_pause_sources_are_the_exact_two_canonical_active_sentinels() -> None:
    assert main._PAUSE_SENTINELS == {
        "mac": Path.home() / ".sapphire" / "autonomous_trading_pause",
        "windows": Path.home() / "ops-state" / "rh-chain" / "killswitch",
    }


def test_pause_clear_cannot_be_fabricated_from_filesystem_mtime(
    tmp_path: Path,
) -> None:
    observations = []
    for source in ("mac", "windows"):
        candidate = tmp_path / f"{source}.json"
        candidate.write_text(json.dumps({"state": "clear"}), encoding="utf-8")
        observations.append(main._pause_file_observation(source, candidate))

    resolved = main._evaluate_pause_truth(
        [item for item in observations if item is not None],
        now=NOW,
    )

    assert all(
        item == {"source": source, "state": "invalid", "observed_at": None}
        for source, item in zip(("mac", "windows"), observations, strict=True)
    )
    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_symlinked_pause_documents_never_clear_the_gate(tmp_path: Path) -> None:
    target = tmp_path / "attacker-controlled.json"
    target.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    observations = []
    for source in ("mac", "windows"):
        candidate = tmp_path / f"{source}.json"
        os.symlink(target, candidate)
        observations.append(main._pause_file_observation(source, candidate))

    resolved = main._evaluate_pause_truth(
        [item for item in observations if item is not None],
        now=NOW,
    )

    assert all(
        item == {"source": source, "state": "invalid", "observed_at": None}
        for source, item in zip(("mac", "windows"), observations, strict=True)
    )
    assert resolved["state"] == "unknown"
    assert resolved["clear"] is None


def test_group_or_world_writable_pause_document_is_unverifiable(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "pause.json"
    candidate.write_text(
        json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
        encoding="utf-8",
    )
    candidate.chmod(0o666)

    assert main._pause_file_observation("mac", candidate) == {
        "source": "mac",
        "state": "invalid",
        "observed_at": None,
    }


def test_stale_parent_expires_future_skewed_agent_claim() -> None:
    observed = NOW
    sample = _sample(observed_at=observed.isoformat(), sequence=9301)
    sample["agents"][0]["updated_at"] = (
        observed + timedelta(seconds=50)
    ).isoformat()
    snapshot = validate_snapshot(sample)
    store = _store(snapshot, received_at=observed.timestamp())

    result = store.get(now=(observed + timedelta(seconds=181)).timestamp())

    assert result["status"] == "stale"
    assert result["agents"][0]["state"] == "offline"
    assert result["agents"][0]["verification"] == "pending"


def test_local_fallback_uses_canonical_parent_aging(monkeypatch) -> None:
    old = NOW - timedelta(minutes=10)
    sample = _sample(observed_at=old.isoformat(), sequence=9302)
    sample["markets"]["decision_gate"] = "manual"
    sample["markets"]["execution"] = "gated"
    sample["desk"]["execution"] = "gated"
    sample["desk"]["autonomy"] = {
        "desired": "on",
        "active": True,
        "new_entries": "available",
        "reason": "stale runtime claim",
    }
    monkeypatch.setattr(
        local_dashboard_server,
        "build_snapshot",
        lambda *_args, **_kwargs: sample,
    )
    monkeypatch.setattr(local_dashboard_server.time, "time", lambda: NOW.timestamp())

    projected = local_dashboard_server._build_live_snapshot()

    assert projected["status"] == "stale"
    assert projected["markets"]["decision_gate"] == "unknown"
    assert projected["markets"]["execution"] == "unknown"
    assert projected["desk"]["execution"] == "unknown"
    assert projected["desk"]["autonomy"]["active"] is False


def test_local_fallback_absence_is_unknown_and_readiness_is_shared() -> None:
    moss = local_dashboard_server._empty_moss_snapshot()
    fleet = local_dashboard_server._empty_fleet_counts()

    assert moss["observed_at"] is None
    assert fleet == {
        "public_view": True,
        "leases": None,
        "gates_open": None,
        "snapshot_age_s": None,
    }
    assert local_dashboard_server._runtime_readiness() == main._readiness_snapshot()


def test_stale_fleet_snapshot_withdraws_current_values() -> None:
    old = NOW - timedelta(hours=1)
    raw = {
        "generated_at": old.isoformat(),
        "leases": [
            {
                "agent": "stale-agent",
                "repo": "stale-repo",
                "purpose": "stale-purpose",
                "expires_at": old.isoformat(),
            }
        ],
        "gates": [
            {"id": 1, "title": "stale gate", "age_hours": 1, "status": "open"}
        ],
    }

    projected = main._whitelist_fleet(raw, now=NOW)

    assert projected == {
        "generated_at": old.isoformat(),
        "leases": [],
        "gates": [],
        "counts": {"leases": None, "gates_open": None},
    }


def test_readiness_pins_task065_source_and_negative_runtime_outcome() -> None:
    assert main._RUNTIME_READINESS["task065"] == {
        "status": "SOURCE_MERGED_INERT",
        "reviewed_head": "2d76f2a3254e5d21ca917a01f945ab1b64912aa0",
        "merged_commit": "f19270df630ef0cb67d439e00e07e70121dae4de",
        "result_sha256": (
            "5fba3c1802fa75ea49801fedb07f4a48cdeaefbe7ef8cd776621f6b8e5b5e916"
        ),
        "review_sha256": (
            "49367a90974b4c4605aa2d2c5e004c7cec9eb0841e73062d16f8bf14f2277cfc"
        ),
        "outcome": "TWO_ATTENDANCES_REQUIRED",
        "one_attendance": "UNAVAILABLE",
        "production_execution": "UNAVAILABLE",
    }


def test_public_source_copy_does_not_claim_unavailable_execution_is_running() -> None:
    repo = Path(__file__).parents[2]
    source = "\n".join(
        candidate.read_text(encoding="utf-8")
        for candidate in (
            repo / "web/src/app/architecture/page.tsx",
            repo / "web/src/app/trading/page.tsx",
            repo / "web/src/data/metrics.ts",
        )
    )
    for live_claim in (
        "runs inference, free-reign policy ticks, and order placement",
        "Both act only inside caps and designated envelopes",
        "When armed, the policy layer auto-approves",
        "GPU executor hosts the schtasks plant",
        "Model inference, free-reign plant, RH/L2 execution under caps",
    ):
        assert live_claim not in source

"""Task 093 R4 goldens for the sealed R3 hostile-review findings.

These probes are source-only. They exercise persisted telemetry projection and
never reach a provider, runtime service, credential, message transport,
broker, wallet, order, or trade adapter.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import live_telemetry
import local_dashboard_server
import main
from live_telemetry import (
    LiveTelemetryStore,
    MemoryTelemetryPersistence,
    validate_snapshot,
)
from tests.test_live_telemetry import _sample


NOW = datetime.now(UTC) - timedelta(seconds=5)


def _store(raw: dict) -> LiveTelemetryStore:
    persistence = MemoryTelemetryPersistence()
    persistence.accept(
        validate_snapshot(raw),
        nonce=f"task093-r4-{raw['sequence']}",
        received_at=NOW.timestamp(),
    )
    return LiveTelemetryStore(persistence)


def test_future_parent_inside_ingest_skew_never_projects_live() -> None:
    future = datetime.now(UTC) + timedelta(seconds=30)
    projected = _store(_sample(observed_at=future.isoformat(), sequence=9401)).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["status"] == "offline"
    assert projected["observed_at"] is None
    assert projected["freshness_s"] is None
    assert projected["summary"]["active_agents"] is None


def test_future_nested_agent_is_withdrawn_from_current_parent() -> None:
    raw = _sample(observed_at=NOW.isoformat(), sequence=9402)
    raw["summary"]["active_agents"] = 1
    raw["agents"][0]["updated_at"] = (
        datetime.now(UTC) + timedelta(seconds=30)
    ).isoformat()

    projected = _store(raw).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["status"] == "live"
    assert projected["agents"][0]["state"] == "offline"
    assert projected["agents"][0]["verification"] == "pending"
    assert projected["summary"]["active_agents"] is None


def test_future_dated_desk_and_event_claims_are_withdrawn() -> None:
    raw = _sample(observed_at=NOW.isoformat(), sequence=9407)
    future = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
    raw["desk"]["updated_at"] = future
    raw["events"][0]["observed_at"] = future

    projected = _store(raw).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["desk"]["posture"] == "unknown"
    assert projected["desk"]["epistemics"] == live_telemetry._epistemics(None)
    assert projected["events"] == []


def test_impossible_current_agent_summary_is_withdrawn() -> None:
    raw = _sample(observed_at=NOW.isoformat(), sequence=9403)
    raw["summary"]["active_agents"] = 99

    projected = _store(raw).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )

    assert projected["agents"][0]["state"] == "working"
    assert projected["summary"]["state"] == "degraded"
    assert projected["summary"]["active_agents"] is None


def test_stale_only_and_mixed_agent_summaries_are_withdrawn() -> None:
    stale_only = _sample(observed_at=NOW.isoformat(), sequence=9404)
    stale_only["summary"]["active_agents"] = 1
    stale_only["agents"][0]["updated_at"] = (
        NOW - timedelta(hours=1)
    ).isoformat()

    mixed = _sample(observed_at=NOW.isoformat(), sequence=9405)
    mixed["summary"]["active_agents"] = 2
    mixed["agents"][0]["updated_at"] = (NOW - timedelta(hours=1)).isoformat()
    mixed["agents"].append(
        {
            **mixed["agents"][0],
            "id": "current-agent",
            "role": "Current observer",
            "state": "working",
            "updated_at": NOW.isoformat(),
        }
    )

    stale_projection = _store(stale_only).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )
    mixed_projection = _store(mixed).get(
        now=(NOW + timedelta(seconds=1)).timestamp(),
        stale_after_seconds=180,
    )

    assert stale_projection["summary"]["active_agents"] is None
    assert mixed_projection["summary"]["active_agents"] is None
    assert [agent["state"] for agent in mixed_projection["agents"]] == [
        "offline",
        "working",
    ]


def test_malformed_persisted_agent_is_removed_and_withdraws_summary() -> None:
    projected = validate_snapshot(_sample(observed_at=NOW.isoformat(), sequence=9406))
    projected["summary"]["active_agents"] = 1
    projected["agents"].append("not-an-agent")

    live_telemetry._age_runtime_projection(
        projected,
        now=(NOW + timedelta(seconds=1)).timestamp(),
        snapshot_observed_at=NOW.timestamp(),
        stale_after_seconds=180,
    )

    assert all(isinstance(agent, dict) for agent in projected["agents"])
    assert projected["summary"]["state"] == "degraded"
    assert projected["summary"]["active_agents"] is None


def test_deeply_nested_admitted_json_returns_canonical_offline(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "deep.json"
    candidate.write_text(
        '{"state":"clear","observed_at":'
        + ("[" * 2_000)
        + '"not-a-semantic-timestamp"'
        + ("]" * 2_000)
        + "}",
        encoding="utf-8",
    )
    candidate.chmod(0o600)

    projected = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=NOW.timestamp(),
    )

    assert projected["status"] == "offline"
    assert projected["observed_at"] is None
    assert projected["freshness_s"] is None


def test_decoder_recursion_error_returns_canonical_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "decoder-recursion.json"
    candidate.write_text(json.dumps({"version": 1}), encoding="utf-8")
    candidate.chmod(0o600)

    def recursion_error(*_args: object, **_kwargs: object) -> object:
        raise RecursionError("hostile decoder recursion")

    monkeypatch.setattr(main.json, "loads", recursion_error)
    projected = local_dashboard_server._build_live_snapshot(
        snapshot_path=candidate,
        now=NOW.timestamp(),
    )

    assert projected["status"] == "offline"
    assert projected["observed_at"] is None

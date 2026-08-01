"""Golden privacy and fidelity tests for the home-mesh projector."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from live_telemetry import validate_snapshot
from telemetry.collector import (
    PUBLIC_EDGE_HEALTH_URL,
    Sources,
    build_snapshot,
    configured_latencies,
    signed_headers,
)


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
    assert snapshot["markets"]["execution"] == "unknown"
    assert snapshot["agents"] == []
    assert any(event["label"] == "Orderflow status observed" for event in snapshot["events"])
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


def test_projector_uses_reduced_agent_presence_as_live_activity(tmp_path):
    missing = tmp_path / "missing.json"
    presence = _write(
        tmp_path / "agent-presence.json",
        {
            "version": 1,
            "observed_at": datetime.fromtimestamp(NOW - 2, UTC).isoformat(),
            "summary": {"active": 1, "blocked": 0, "verified": 1},
            "agents": [
                {
                    "role": "Local build agent",
                    "state": "verifying",
                    "activity": "Golden evals and scope verified",
                    "verification": "verified",
                    "provider_class": "local GPU",
                    "updated_at": datetime.fromtimestamp(NOW - 3, UTC).isoformat(),
                }
            ],
            "events": [
                {
                    "occurred_at": datetime.fromtimestamp(NOW - 3, UTC).isoformat(),
                    "event_type": "verification.passed",
                    "phase": "verifying",
                    "actor_role": "Local build agent",
                    "provider_class": "local GPU",
                    "source": "harness",
                    "status": "verified",
                    "verification": "verified",
                    "label": "Golden evals and scope verified",
                    "activity_band": "light",
                    "duration_band": "under 100 ms",
                }
            ],
            "source_errors": 0,
        },
    )
    snapshot = validate_snapshot(
        build_snapshot(
            Sources(missing, missing, missing, missing, missing, missing, presence),
            now=NOW,
        )
    )

    assert snapshot["agents"][0]["role"] == "Local build agent"
    assert snapshot["agents"][0]["state"] == "verifying"
    assert snapshot["agents"][0]["activity"] == "Capability result under verification"
    assert snapshot["events"][0]["label"] == "Agent result verified"
    assert snapshot["events"][0]["status"] == "verified"
    # Presence is the only source that classifies task-executing agents. The
    # unrelated service-health files are not prerequisites for this count.
    assert snapshot["summary"]["active_agents"] == 1
    intelligence = next(node for node in snapshot["nodes"] if node["id"] == "intelligence")
    assert intelligence["status"] == "healthy"
    assert intelligence["activity_rate"] > 0


def test_current_service_health_does_not_turn_stale_presence_into_known_zero(tmp_path):
    """Fresh service health cannot attest that an old task roster is empty."""
    missing = tmp_path / "missing.json"
    stale_time = datetime.fromtimestamp(NOW - 86_400, UTC).isoformat()
    presence = _write(
        tmp_path / "agent-presence.json",
        {
            "version": 1,
            "observed_at": stale_time,
            "summary": {"active": 0, "blocked": 0, "verified": 0},
            "agents": [
                {
                    "role": "Local build agent",
                    "state": "offline",
                    "activity": "No task assigned",
                    "verification": "not_applicable",
                    "provider_class": "local GPU",
                    "updated_at": stale_time,
                }
            ],
            "events": [],
            "source_errors": 0,
        },
    )
    health = _write(
        tmp_path / "health.json",
        {"generated_ts": NOW - 4, "overall": "healthy", "agents": []},
    )

    snapshot = validate_snapshot(
        build_snapshot(
            Sources(
                health, missing, missing, missing, missing, missing, presence),
            now=NOW,
        )
    )
    intelligence = next(
        node for node in snapshot["nodes"] if node["id"] == "intelligence")

    assert intelligence["status"] == "healthy"
    assert intelligence["freshness_s"] == 4
    assert intelligence["activity_rate"] is None
    assert snapshot["agents"] == []
    assert snapshot["summary"]["active_agents"] is None


def test_fresh_complete_empty_presence_is_a_measured_zero(tmp_path):
    missing = tmp_path / "missing.json"
    presence = _write(
        tmp_path / "agent-presence.json",
        {
            "version": 1,
            "observed_at": datetime.fromtimestamp(NOW - 2, UTC).isoformat(),
            "summary": {"active": 0, "blocked": 0, "verified": 0},
            "agents": [],
            "events": [],
            "source_errors": 0,
        },
    )

    snapshot = validate_snapshot(
        build_snapshot(
            Sources(missing, missing, missing, missing, missing, missing, presence),
            now=NOW,
        )
    )
    intelligence = next(
        node for node in snapshot["nodes"] if node["id"] == "intelligence"
    )
    agent_link = next(
        link
        for link in snapshot["links"]
        if (link["source"], link["target"]) == ("gpu-compute", "intelligence")
    )

    assert snapshot["summary"]["active_agents"] == 0
    assert snapshot["agents"] == []
    assert intelligence["activity_rate"] == 0.0
    assert agent_link["event_rate"] == 0.0


def test_fresh_unavailable_presence_projection_withholds_all_agent_metrics(tmp_path):
    """A projector read error stays unknown even when its envelope is fresh."""
    missing = tmp_path / "missing.json"
    presence = _write(
        tmp_path / "agent-presence.json",
        {
            "version": 1,
            "observed_at": datetime.fromtimestamp(NOW - 2, UTC).isoformat(),
            "summary": {"active": 0, "blocked": 0, "verified": 0},
            "agents": [],
            "events": [],
            "source_errors": 1,
        },
    )

    snapshot = validate_snapshot(
        build_snapshot(
            Sources(missing, missing, missing, missing, missing, missing, presence),
            now=NOW,
        )
    )
    intelligence = next(
        node for node in snapshot["nodes"] if node["id"] == "intelligence"
    )
    agent_link = next(
        link
        for link in snapshot["links"]
        if (link["source"], link["target"]) == ("gpu-compute", "intelligence")
    )

    assert snapshot["summary"]["active_agents"] is None
    assert intelligence["activity_rate"] is None
    assert agent_link["event_rate"] is None


def test_presence_rewrite_ages_stale_blocked_work_out_of_current_state(tmp_path):
    missing = tmp_path / "missing.json"
    fresh_snapshot_time = datetime.fromtimestamp(NOW, UTC).isoformat()
    stale_agent_time = datetime.fromtimestamp(NOW - 1_000, UTC).isoformat()
    presence = _write(
        tmp_path / "agent-presence.json",
        {
            "version": 1,
            "observed_at": fresh_snapshot_time,
            "summary": {"active": 0, "blocked": 1, "verified": 0},
            "agents": [
                {
                    "role": "Build observer",
                    "state": "blocked",
                    "activity": "Build proposal refused",
                    "verification": "not_applicable",
                    "provider_class": "local CPU",
                    "updated_at": stale_agent_time,
                }
            ],
            "events": [],
            "source_errors": 0,
        },
    )

    snapshot = validate_snapshot(
        build_snapshot(Sources(missing, missing, missing, missing, missing, missing, presence), now=NOW)
    )
    intelligence = next(node for node in snapshot["nodes"] if node["id"] == "intelligence")
    # A fresh projection with an old task timestamp is a current observation
    # that no task is still active. It cannot leave the live system degraded
    # forever because a blocked run existed in the past.
    assert intelligence["status"] == "healthy"
    assert intelligence["freshness_s"] == 0
    assert snapshot["agents"] == []
    assert snapshot["summary"]["active_agents"] == 0
    # A blocked component is not evidence that a human decision is queued.
    assert snapshot["summary"]["attention"] is None


def test_service_daemons_do_not_count_as_active_agents_and_degradation_propagates(
    tmp_path,
):
    """Service process liveness is not agent work, and it cannot mask a fault.

    The RH health producer calls its monitored daemons ``agents`` for historical
    reasons. The public aggregate must count only the real presence roles while
    still carrying the worst daemon health into the intelligence node and the
    system summary.
    """
    services = [
        {"label": "Chain Poll", "status": "degraded"},
        {"label": "Orderflow", "status": "degraded"},
        *[
            {"label": label, "status": "healthy"}
            for label in (
                "Feed Listen",
                "Clean Watchlist",
                "Fresh Decay",
                "Metrics Advisory",
                "Social Signal",
                "Visualizer Serve",
            )
        ],
    ]
    presence = {
        "version": 1,
        "observed_at": datetime.fromtimestamp(NOW - 2, UTC).isoformat(),
        "summary": {"active": 0, "blocked": 0, "verified": 0},
        "agents": [
            {
                "role": "Local build agent",
                "state": "idle",
                "activity": "No task assigned",
                "verification": "not_applicable",
                "provider_class": "local GPU",
                "updated_at": datetime.fromtimestamp(NOW - 3, UTC).isoformat(),
            }
        ],
        "events": [],
        "source_errors": 0,
    }
    sources = Sources(
        rh_health=_write(
            tmp_path / "health.json",
            {"generated_ts": NOW - 4, "overall": "degraded", "agents": services},
        ),
        rh_feed=_write(
            tmp_path / "feed.json",
            {"updated": NOW - 2, "msgs_per_min": 88},
        ),
        memes=_write(tmp_path / "memes.json", {"updated": NOW - 1}),
        paper=_write(tmp_path / "paper.json", {"updated": NOW - 3}),
        gpu=_write(
            tmp_path / "gpu.json",
            {
                "updated": NOW - 3,
                "status": "up",
                "services": {"ollama": 1, "worker": 1},
            },
        ),
        desk_cycle=_write(
            tmp_path / "desk.json",
            {
                "finished_at": datetime.fromtimestamp(NOW - 3, UTC).isoformat(),
                "status": "ok",
                "totals": {"inserted": 0},
            },
        ),
        agent_presence=_write(tmp_path / "presence.json", presence),
    )

    snapshot = validate_snapshot(build_snapshot(sources, now=NOW))
    intelligence = next(
        node for node in snapshot["nodes"] if node["id"] == "intelligence"
    )

    assert snapshot["summary"]["active_agents"] == 0
    assert intelligence["status"] == "degraded"
    assert snapshot["summary"]["state"] == "degraded"
    assert snapshot["agents"][0]["role"] == "Local build agent"
    assert all(agent["role"] not in {"Chain Poll", "Orderflow"} for agent in snapshot["agents"])
    event_labels = {event["label"] for event in snapshot["events"]}
    assert {"Chain Poll status observed", "Orderflow status observed"} <= event_labels
    service_events = [
        event
        for event in snapshot["events"]
        if event["label"] in {"Chain Poll status observed", "Orderflow status observed"}
    ]
    assert service_events
    assert all(event["event_class"] == "reliability" for event in service_events)


def test_default_edge_probe_targets_the_public_api_health_route(monkeypatch):
    monkeypatch.delenv("SAPPHIRE_EDGE_PROBE", raising=False)
    seen: list[str] = []

    configured_latencies(
        http_probe=lambda url, **_kwargs: seen.append(url) or 1.0,
        gateway_probe=lambda _url, **_kwargs: 2.0,
    )

    assert PUBLIC_EDGE_HEALTH_URL == "https://sapphirealpha.xyz/api/health"
    assert seen == [PUBLIC_EDGE_HEALTH_URL]

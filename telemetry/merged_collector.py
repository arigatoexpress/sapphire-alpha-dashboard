"""Merge Mac fleet + Windows workhorse snapshots into one Sapphire Mission Snapshot.

Reads the Mac ops-state via telemetry/collector.py and the Windows workhorse via
telemetry/win_collector.py (run over SSH), merges agents/nodes/links/events, and
pushes a single signed snapshot so both sources are visible simultaneously.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))

from collector import build_snapshot as build_mac_snapshot  # noqa: E402
from collector import Sources as MacSources  # noqa: E402
from collector import configured_latencies as mac_configured_latencies  # noqa: E402
from collector import public_semantic_text  # noqa: E402
from collector import push  # noqa: E402
from live_telemetry import validate_snapshot  # noqa: E402


def _ssh_win_snapshot(win_home: str = "C:\\Users\\aribs") -> dict:
    """Run the Windows collector in print-only mode and return its snapshot."""
    cmd = [
        "ssh",
        "-o", "ConnectTimeout=10",
        "win",
        f"python {win_home}\\.sapphire\\win_collector.py --compact",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"win_collector failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _sanitize_windows_snapshot(snapshot: dict) -> dict:
    """Quarantine unproven numeric rates from the deployed Windows collector.

    The Windows copy currently reached over SSH predates measured-rate
    instrumentation. Its node/link rates are deterministic multipliers of GPU
    utilization, model count, queue depth, and cumulative task count. The wire
    has no provenance/version flag that can distinguish those proxies from a
    later measured implementation, so the safe merged view withdraws every
    remote activity/event rate until that contract is versioned.

    Latency is deliberately preserved: the Windows inference latency is a
    timed request round trip, not one of the proxy values. Arbitrary remote prose
    is also bounded before it can enter the public snapshot.
    """
    sanitized = copy.deepcopy(snapshot)

    for node in sanitized.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node["activity_rate"] = None
        node["label"] = public_semantic_text(
            node.get("label"),
            fallback="Windows component",
            limit=64,
        )

    for link in sanitized.get("links", []):
        if isinstance(link, dict):
            link["event_rate"] = None

    agents = sanitized.get("agents")
    if isinstance(agents, list):
        for index, agent in enumerate(agents):
            if not isinstance(agent, dict):
                continue
            original_role = agent.get("role")
            safe_role = public_semantic_text(
                original_role,
                fallback="Windows agent",
                limit=64,
            )
            agent["role"] = safe_role
            if safe_role != original_role:
                agent["id"] = f"windows-agent-{index + 1}"
            agent["activity"] = public_semantic_text(
                agent.get("activity"),
                fallback="Windows agent state observed",
                limit=120,
            )

    events = sanitized.get("events")
    if isinstance(events, list):
        for event in events:
            if isinstance(event, dict):
                event["label"] = public_semantic_text(
                    event.get("label"),
                    fallback="Windows activity observed",
                    limit=120,
                )

    summary = sanitized.get("summary")
    if isinstance(summary, dict):
        summary["events_per_min"] = None
        summary["verified_today"] = None
        summary["attention"] = None
        summary["active_agents"] = (
            sum(
                1
                for agent in agents
                if isinstance(agent, dict) and agent.get("state") in {"working", "verifying"}
            )
            if isinstance(agents, list) and len(agents) <= 32
            else None
        )

    markets = sanitized.get("markets")
    if isinstance(markets, dict):
        markets["feed_age_s"] = None
        markets["events_per_min"] = None
        markets["paper_strategies"] = None

    desk = sanitized.get("desk")
    unknown_desk = (
        isinstance(desk, dict)
        and desk.get("updated_at") is None
        and desk.get("posture") == "unknown"
        and desk.get("leader") == "unknown"
        and desk.get("execution") == "unknown"
        and isinstance(desk.get("validation"), dict)
        and all(
            desk["validation"].get(key) is None
            for key in ("oos_pass", "oos_total", "conflicts")
        )
        and isinstance(desk.get("feeds"), dict)
        and all(desk["feeds"].get(key) is None for key in ("fresh", "total"))
    )
    if not isinstance(desk, dict) or unknown_desk:
        sanitized.pop("desk", None)

    return sanitized


def _sequence(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _merge_snapshots(mac: dict, win: dict) -> dict:
    """Merge two schema-v1 snapshots. Mac is authoritative for markets/summary base."""
    merged = copy.deepcopy(mac)
    win = _sanitize_windows_snapshot(win)

    # Merge agents by id
    agent_by_id = {agent["id"]: agent for agent in mac.get("agents", [])}
    for agent in win.get("agents", []):
        agent_by_id[agent["id"]] = agent
    merged_agents = list(agent_by_id.values())
    merged["agents"] = merged_agents[:32]

    # Merge nodes by id
    node_by_id = {node["id"]: node for node in mac.get("nodes", [])}
    for node in win.get("nodes", []):
        node_by_id[node["id"]] = node
    merged["nodes"] = list(node_by_id.values())[:24]

    # Merge links by (source, target)
    link_by_key = {(link["source"], link["target"]): link for link in mac.get("links", [])}
    for link in win.get("links", []):
        link_by_key[(link["source"], link["target"])] = link
    merged["links"] = list(link_by_key.values())[:48]

    # Merge events by id, most recent first
    event_by_id = {event["id"]: event for event in mac.get("events", [])}
    for event in win.get("events", []):
        event_by_id[event["id"]] = event
    merged["events"] = sorted(
        event_by_id.values(),
        key=lambda e: e.get("observed_at", ""),
        reverse=True,
    )[:100]

    # Mac presence is the only source that classifies actual task agents.
    # Windows currently reports services (bot, model host, GPU, task runner) in
    # the same collection, so counting merged rows would turn daemons into
    # "active agents." Preserve the classified presence count until Windows
    # publishes a service-vs-agent discriminator.
    mac_summary = mac.get("summary", {})
    win_summary = win.get("summary", {})
    active = mac_summary.get("active_agents")
    if not isinstance(active, int) or isinstance(active, bool):
        active = None
    win_desk = win.get("desk")
    decisions = win_desk.get("decisions") if isinstance(win_desk, dict) else None
    attention = (
        decisions.get("pending_review")
        if isinstance(decisions, dict)
        else None
    )
    if (
        not isinstance(attention, int)
        or isinstance(attention, bool)
        or not 0 <= attention <= 1_000
    ):
        attention = None
    merged["summary"] = {
        "state": (
            "degraded"
            if "degraded" in {mac_summary.get("state"), win_summary.get("state")}
            else mac_summary.get("state", "observing")
        ),
        "active_agents": None if active is None else min(active, 100),
        "events_per_min": None,
        "verified_today": None,
        "attention": attention,
    }

    # Sequence must increase across pushes
    merged["sequence"] = max(_sequence(mac.get("sequence")), _sequence(win.get("sequence"))) + 1
    observations = [
        observed
        for observed in (mac.get("observed_at"), win.get("observed_at"))
        if isinstance(observed, str)
    ]
    merged["observed_at"] = max(observations) if observations else mac.get("observed_at")
    if isinstance(win_desk, dict):
        merged["desk"] = copy.deepcopy(win_desk)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge Mac + Windows telemetry into one Sapphire snapshot")
    parser.add_argument("--push", action="store_true", help="submit to SAPPHIRE_TELEMETRY_ENDPOINT")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--validate-only", action="store_true", help="build snapshot and exit 0 if valid")
    args = parser.parse_args()

    mac_snapshot = build_mac_snapshot(
        MacSources.defaults(),
        link_latencies=mac_configured_latencies(),
    )
    # The Windows leg goes over SSH to a box that sleeps. run_publisher.sh has
    # always claimed this degrades to Mac-only, but the call was unguarded and
    # RuntimeError from an unreachable host propagated straight out of main():
    # box asleep -> publisher exits non-zero -> nothing is published -> the live
    # feed goes stale, from a machine being off. Half a snapshot beats none.
    try:
        win_snapshot = _ssh_win_snapshot()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"WARN windows telemetry leg unavailable, publishing Mac-only: {exc}", file=sys.stderr)
        win_snapshot = None
    snapshot = _merge_snapshots(mac_snapshot, win_snapshot) if win_snapshot else mac_snapshot
    # Validate locally before an outbound push. Keep the original raw shape:
    # validate_snapshot intentionally projects an absent desk as honest
    # unknown state, while omitting the raw desk is what remains compatible
    # with older deployed validators.
    validate_snapshot(snapshot)

    if args.validate_only:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
        return 0

    if args.push:
        endpoint = os.environ.get("SAPPHIRE_TELEMETRY_ENDPOINT", "").strip()
        secret = os.environ.get("TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit("SAPPHIRE_TELEMETRY_ENDPOINT is required with --push")
        if not secret:
            raise SystemExit("TELEMETRY_INGEST_SECRET is required with --push")
        print(json.dumps(push(snapshot, endpoint=endpoint, secret=secret), sort_keys=True))
    else:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

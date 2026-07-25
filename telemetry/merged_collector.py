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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collector import build_snapshot as build_mac_snapshot
from collector import Sources as MacSources
from collector import configured_latencies as mac_configured_latencies
from collector import push


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


def _merge_snapshots(mac: dict, win: dict) -> dict:
    """Merge two schema-v1 snapshots. Mac is authoritative for markets/summary base."""
    merged = copy.deepcopy(mac)

    # Merge agents by id
    agent_by_id = {agent["id"]: agent for agent in mac.get("agents", [])}
    for agent in win.get("agents", []):
        agent_by_id[agent["id"]] = agent
    merged["agents"] = list(agent_by_id.values())[:32]

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

    # Summary: sum active agents, max attention, keep Mac state as baseline
    mac_summary = mac.get("summary", {})
    win_summary = win.get("summary", {})
    active = mac_summary.get("active_agents", 0) + win_summary.get("active_agents", 0)
    attention = mac_summary.get("attention", 0) + win_summary.get("attention", 0)
    verified = mac_summary.get("verified_today", 0) + win_summary.get("verified_today", 0)
    events_per_min = mac_summary.get("events_per_min", 0) + win_summary.get("events_per_min", 0)
    merged["summary"] = {
        "state": mac_summary.get("state", "observing"),
        "active_agents": min(active, 100),
        "events_per_min": events_per_min,
        "verified_today": verified,
        "attention": min(attention, 100),
    }

    # Sequence must increase across pushes
    merged["sequence"] = max(mac.get("sequence", 0), win.get("sequence", 0)) + 1
    merged["observed_at"] = max(mac.get("observed_at", ""), win.get("observed_at", ""))
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
    win_snapshot = _ssh_win_snapshot()
    snapshot = _merge_snapshots(mac_snapshot, win_snapshot)

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

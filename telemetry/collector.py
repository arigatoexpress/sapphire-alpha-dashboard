"""Project raw local observations into the public-safe Mission Snapshot.

Raw files are read locally and never transmitted. The output vocabulary is
deliberately semantic: roles, health, freshness, activity, and verification.
There is no actuation path in this module.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import time
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Mapping

try:  # running as a package (backend tests, `python -m telemetry.collector`)
    from telemetry import probes
except ImportError:  # running the file directly, as the LaunchAgent does
    import probes  # type: ignore[no-redef]


# The public edge answers this from anywhere, so the round trip the orchestration
# host measures against it is the real network leg between those two components.
# Use the API alias because Google Front End may intercept /healthz on Cloud Run,
# while /api/health is an application route on both the service and custom domain.
PUBLIC_EDGE_HEALTH_URL = "https://sapphirealpha.xyz/api/health"
# The GPU gateway publishes its tiers here and routes to the first healthy one.
GPU_GATEWAY_HEALTH_URL = "http://127.0.0.1:8800/healthz"

# Most sources on this host are refreshed every minute or two, so a quarter hour
# without an update means something stopped.
DEFAULT_SOURCE_STALE_AFTER_SECONDS = 900
# The desk cycle is a batch job, not a heartbeat: `com.ari.deskos-cycle` runs on
# StartInterval 21600. Judging it against the 900 s ceiling above marked it
# "down" for 5 h 45 m of every 6 h cycle — red 95.8% of the time, on a source
# reporting `status: ok` with zero errors. A check that is always red trains
# everyone to ignore it, so a real outage reads as the usual noise. A periodic
# job is healthy while its last success is inside two cadences, which tolerates
# exactly one missed run and nothing more. Paired with the plist and asserted by
# backend/tests/test_link_instrumentation.py.
DESK_CYCLE_INTERVAL_SECONDS = 21_600
DESK_CYCLE_STALE_AFTER_SECONDS = DESK_CYCLE_INTERVAL_SECONDS * 2

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\w)"
)
_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,32}\b")
_SENSITIVE_TEXT = (
    "http://",
    "https://",
    "/users/",
    "c:\\users",
    "localhost",
    "ts.net",
)


@dataclass(frozen=True)
class Sources:
    rh_health: Path
    rh_feed: Path
    memes: Path
    paper: Path
    gpu: Path
    desk_cycle: Path
    agent_presence: Path | None = None

    @classmethod
    def defaults(cls) -> "Sources":
        ops = Path(os.getenv("SAPPHIRE_OPS_STATE", Path.home() / "ops-state"))
        chain = ops / "rh-chain"
        return cls(
            rh_health=chain / "agent-health-state.json",
            rh_feed=chain / "rh-feed-state.json",
            memes=chain / "memes-state.json",
            paper=chain / "paper-state.json",
            gpu=ops / "gpu-node-status.json",
            desk_cycle=ops / "deskos" / "last_cycle.json",
            agent_presence=ops / "agent-presence.json",
        )


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
            except ValueError:
                return None
    return None


def _age(now: float, *candidates: Any) -> float:
    timestamps = [parsed for value in candidates if (parsed := _epoch(value)) is not None]
    return round(max(0.0, now - max(timestamps)), 3) if timestamps else 86_400.0


def _health(value: Any, *, age_s: float, stale_after_s: float = DEFAULT_SOURCE_STALE_AFTER_SECONDS) -> str:
    if age_s > stale_after_s:
        return "down"
    normalized = str(value or "unknown").lower()
    if normalized in {"healthy", "ok", "up", "live", "running", "current"}:
        return "healthy"
    if normalized in {"degraded", "warn", "warning", "partial"}:
        return "degraded"
    if normalized in {"down", "failed", "offline", "error"}:
        return "down"
    return "unknown"


def _agent_id(label: str, index: int) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in label.lower()).strip("-")
    slug = "-".join(filter(None, slug.split("-")))[:32]
    return slug or f"observer-{index + 1}"


def public_semantic_text(value: Any, *, fallback: str, limit: int) -> str:
    """Return bounded public prose, replacing text that can identify a person.

    Presence and remote collectors are local inputs, not a trusted public
    vocabulary. Keeping their arbitrary strings would let an email address,
    phone number, handle, endpoint, or home path become public through a role,
    activity, or event label. The backend rejects the same classes at ingest;
    collectors replace them first so one poisoned local record cannot take the
    whole telemetry push down.
    """
    if not isinstance(value, str):
        return fallback
    candidate = " ".join(value.split()).strip()
    lowered = candidate.lower()
    if (
        not candidate
        or len(candidate) > limit
        or any(marker in lowered for marker in _SENSITIVE_TEXT)
        or _EMAIL_RE.search(candidate)
        or _PHONE_RE.search(candidate)
        or _HANDLE_RE.search(candidate)
    ):
        return fallback
    return candidate


def _presence_agents(value: dict[str, Any]) -> list[dict[str, Any]]:
    raw_agents = value.get("agents") if isinstance(value.get("agents"), list) else []
    allowed_states = {"working", "verifying", "idle", "blocked", "offline"}
    allowed_verification = {"verified", "pending", "failed", "not_applicable"}
    allowed_providers = {"local GPU", "local CPU", "cloud reasoning", "hybrid", "rule-only", "unassigned"}
    agents: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_agents[:24]):
        if not isinstance(raw, dict):
            continue
        role = public_semantic_text(raw.get("role"), fallback="Agent observer", limit=64)
        state = str(raw.get("state") or "offline")
        verification = str(raw.get("verification") or "pending")
        provider = str(raw.get("provider_class") or "unassigned")
        updated_at = raw.get("updated_at")
        updated_epoch = _epoch(updated_at)
        if (
            state not in allowed_states
            or verification not in allowed_verification
            or provider not in allowed_providers
            or updated_epoch is None
        ):
            continue
        activity = {
            "working": "Capability route active",
            "verifying": "Capability result under verification",
            "idle": "Capability route waiting",
            "blocked": "Capability route unavailable",
            "offline": "Capability route not observed",
        }[state]
        agents.append(
            {
                "id": _agent_id(role, index),
                "role": role,
                "state": state,
                "activity": activity,
                "verification": verification,
                "provider_class": provider,
                "updated_at": datetime.fromtimestamp(updated_epoch, UTC).isoformat(),
            }
        )
    return agents


def _presence_events(value: dict[str, Any], *, now: float) -> tuple[list[dict[str, Any]], float | None]:
    raw_events = value.get("events") if isinstance(value.get("events"), list) else []
    status_map = {
        "observed": "observed",
        "working": "observed",
        "healthy": "observed",
        "verified": "verified",
        "pending": "pending",
        "failed": "failed",
        "blocked": "degraded",
        "degraded": "degraded",
        "offline": "degraded",
    }
    events: list[dict[str, Any]] = []
    # The presence projector re-runs on every append to the event log
    # (`com.ari.agent-presence-projector` is WatchPaths-driven), so this list is
    # an append-only source: a window with nothing in it means nothing happened,
    # which is a measured zero rather than a blank. `has_source` separates that
    # from "the presence file is not there at all", which is not measurable.
    has_source = isinstance(value.get("events"), list)
    occurrences: list[float] = []
    for index, raw in enumerate(raw_events[-24:]):
        if not isinstance(raw, dict):
            continue
        occurred = _epoch(raw.get("occurred_at"))
        status = status_map.get(str(raw.get("status") or ""))
        if occurred is None or status is None:
            continue
        occurrences.append(occurred)
        events.append(
            {
                "id": f"presence-{index + 1}",
                "observed_at": datetime.fromtimestamp(occurred, UTC).isoformat(),
                "event_class": "agent",
                "source": "intelligence",
                "target": "archive",
                "label": {
                    "verified": "Agent result verified",
                    "failed": "Agent result failed",
                    "degraded": "Agent capability degraded",
                    "pending": "Agent result pending",
                    "observed": "Agent activity observed",
                }[status],
                "status": status,
            }
        )
    # The projector currently retains at most 24 entries. When that list is
    # full, older events inside the five-minute window may have been dropped,
    # so dividing the retained entries by the window would publish a silent
    # undercount. An upstream producer may explicitly attest completeness.
    saturated = len(raw_events) >= 24 and value.get("events_window_complete") is not True
    rate = None if saturated else probes.timestamp_rate_per_min(
        occurrences if has_source else None,
        now=now,
    )
    return events, rate


def _presence_health(agents: list[dict[str, Any]], *, source_errors: int | None = 0) -> str:
    """Health of the agent-presence spine — which is not the same as busyness.

    `state: "offline"` in `agent-presence.json` means only that a role's last
    event is older than the projector's staleness window (ops_server
    `agent_events._public_agent_state`). Those roles are capability-router lanes
    that emit nothing until something routes through them, so all-offline means
    "no work arrived", not "the intelligence layer is broken". Mapping it to
    `down` — as this did — nailed the node red permanently and left the check
    unable to distinguish idle from dead.

    What genuinely indicates trouble: the projector reporting source errors, or a
    role reporting `blocked`. Idle is reported honestly through the node's
    `freshness_s` and its measured event rate, both of which say "nothing for a
    day" without claiming an outage.
    """
    if not agents:
        return "unknown"
    states = {agent["state"] for agent in agents}
    if (source_errors is not None and source_errors > 0) or "blocked" in states:
        return "degraded"
    return "healthy"


def _worst_health(*statuses: str) -> str:
    """Return the least healthy independently observed component status."""
    severity = {"healthy": 0, "unknown": 1, "degraded": 2, "down": 3}
    return max(statuses, key=lambda status: severity.get(status, 1))


def _desk_insert_rate(desk: dict[str, Any], *, desk_age: float) -> float | None:
    """Rows per minute the last desk cycle actually wrote, while it still counts.

    The number is real — rows inserted divided by the cycle's own wall clock —
    but it describes the window the cycle ran in. Once that window falls outside
    the measurement horizon it no longer describes now, and the honest answer
    becomes None. On a six-hourly cadence that is most of the time, which is why
    this edge reads blank far more often than it reads busy. Blank is correct:
    the alternative is republishing a three-hour-old burst as current traffic.
    """
    totals = desk.get("totals")
    inserted = totals.get("inserted") if isinstance(totals, dict) else None
    if isinstance(inserted, bool) or not isinstance(inserted, (int, float)) or inserted < 0:
        return None
    started = _epoch(desk.get("started_at"))
    finished = _epoch(desk.get("finished_at"))
    if started is None or finished is None or finished <= started:
        return None
    return probes.snapshot_measurement(
        float(inserted) / ((finished - started) / 60.0),
        source_age_s=desk_age,
    )


def build_snapshot(
    sources: Sources,
    *,
    now: float | None = None,
    link_latencies: Mapping[str, float | None] | None = None,
) -> dict[str, Any]:
    """Build one schema-v1 snapshot using only bounded semantic fields."""
    now = time.time() if now is None else now
    link_latencies = link_latencies or {}
    observed_at = datetime.fromtimestamp(now, UTC).isoformat()
    rh_health = _read(sources.rh_health)
    feed = _read(sources.rh_feed)
    memes = _read(sources.memes)
    paper = _read(sources.paper)
    gpu = _read(sources.gpu)
    desk = _read(sources.desk_cycle)
    presence = _read(sources.agent_presence) if sources.agent_presence else {}

    rh_age = _age(now, rh_health.get("generated_ts"))
    # The chain feed's age is the chain feed's own timestamp. This used to be
    # max(feed, memes), which let a live memes stream vouch for a dead chain
    # feed: `markets` would read "current", and its latency and message rate
    # would keep being republished, while nothing had arrived from the chain for
    # an hour. A freshness check that another source can satisfy is not a
    # freshness check.
    feed_age = _age(now, feed.get("updated"))
    gpu_age = _age(now, gpu.get("updated"), gpu.get("last_check"))
    desk_age = _age(now, desk.get("finished_at"), desk.get("started_at"))
    presence_agents = _presence_agents(presence)
    presence_events, presence_event_rate = _presence_events(presence, now=now)
    raw_presence_agents = (
        presence.get("agents") if isinstance(presence.get("agents"), list) else None
    )
    raw_agents = rh_health.get("agents") if isinstance(rh_health.get("agents"), list) else []
    agents: list[dict[str, Any]] = list(presence_agents)
    for index, raw in enumerate(raw_agents[:12]):
        if not isinstance(raw, dict):
            continue
        label = public_semantic_text(raw.get("label"), fallback="Research observer", limit=64)
        status = _health(raw.get("status"), age_s=rh_age)
        if any(agent["role"] == label for agent in agents):
            continue
        agents.append(
            {
                "id": _agent_id(label, index),
                "role": label,
                # A degraded observer with a fresh state file is still running;
                # its health belongs in verification and the intelligence-node
                # aggregate. Calling it blocked made recovered RPC throttles
                # look like dead workers even while they published new state.
                "state": "working" if status in {"healthy", "degraded"} else "offline",
                "activity": (
                    "Observing live research signals"
                    if status == "healthy"
                    else "Reporting with source errors"
                    if status == "degraded"
                    else "Awaiting source recovery"
                ),
                "verification": "verified" if status == "healthy" else "failed" if status == "down" else "pending",
                "provider_class": "local CPU",
                "updated_at": datetime.fromtimestamp(max(0, now - rh_age), UTC).isoformat(),
            }
        )

    service_count = sum(1 for value in (gpu.get("services") or {}).values() if bool(value)) if isinstance(gpu.get("services"), dict) else 0
    gpu_status = _health(gpu.get("status"), age_s=gpu_age)
    if gpu:
        agents.append(
            {
                "id": "gpu-workhorse",
                "role": "GPU workhorse",
                "state": "working" if gpu_status == "healthy" and service_count else "offline",
                "activity": f"Serving {service_count} compute lanes" if service_count else "Compute lanes not observed",
                "verification": "verified" if gpu_status == "healthy" else "pending",
                "provider_class": "local GPU",
                "updated_at": datetime.fromtimestamp(max(0, now - gpu_age), UTC).isoformat(),
            }
        )

    market_status = "current" if feed_age <= 60 else "delayed" if feed_age <= 300 else "stale" if feed else "offline"
    market_health = "healthy" if market_status == "current" else "degraded" if market_status in {"delayed", "stale"} else "down"
    source_errors = (
        presence.get("source_errors")
        if isinstance(presence.get("source_errors"), int)
        and not isinstance(presence.get("source_errors"), bool)
        else None
    )
    rh_service_status = _health(rh_health.get("overall"), age_s=rh_age)
    if presence_agents:
        presence_status = _presence_health(
            presence_agents,
            source_errors=source_errors,
        )
        # Presence describes agent work; RH health describes the services that
        # work depends on. Neither source may erase degradation in the other.
        rh_status = (
            _worst_health(presence_status, rh_service_status)
            if rh_health
            else presence_status
        )
    else:
        rh_status = rh_service_status
    intelligence_age = _age(now, *(agent["updated_at"] for agent in presence_agents)) if presence_agents else rh_age
    # Measured agent-event rate, or None. The old fallback here was
    # `len(agents) * 4` — an agent head-count multiplied by a magic number and
    # published as events per minute. That is the kind of number this whole
    # module now exists to refuse.
    agent_rate = presence_event_rate if presence_agents else None
    desk_status = _health(desk.get("status"), age_s=desk_age, stale_after_s=DESK_CYCLE_STALE_AFTER_SECONDS)

    # feed_lag_s is source timestamp lag, not a request/response round trip.
    # Publishing it as latency_ms mislabeled a one-way freshness quantity as
    # network latency. There is no RTT probe on this semantic edge.
    markets_latency_ms = None
    markets_rate = probes.snapshot_measurement(feed.get("msgs_per_min"), source_age_s=feed_age)
    archive_rate = _desk_insert_rate(desk, desk_age=desk_age)
    paper_strategy_count = paper.get("strategy_count")
    if (
        not isinstance(paper_strategy_count, int) or
        isinstance(paper_strategy_count, bool) or
        paper_strategy_count < 0
    ):
        paper_strategy_count = None

    def _fresh(age: float) -> float:
        return min(float(age), 86_400.0)

    nodes = [
        {"id": "public-edge", "zone": "edge", "label": "Public edge", "status": "healthy", "load_band": "low", "activity_rate": None, "freshness_s": 0.0},
        {"id": "orchestration", "zone": "orchestration", "label": "Orchestration", "status": desk_status, "load_band": "medium" if archive_rate and archive_rate > 0 else "idle", "activity_rate": archive_rate, "freshness_s": _fresh(desk_age)},
        {"id": "gpu-compute", "zone": "compute", "label": "GPU compute", "status": gpu_status, "load_band": "medium" if service_count else "idle", "activity_rate": None, "freshness_s": _fresh(gpu_age)},
        {"id": "intelligence", "zone": "intelligence", "label": "Agent intelligence", "status": rh_status, "load_band": "high" if agent_rate is not None and agent_rate >= 60 else "medium" if agent_rate is not None and agent_rate > 0 else "idle", "activity_rate": agent_rate, "freshness_s": _fresh(intelligence_age)},
        {"id": "markets", "zone": "markets", "label": "Robinhood Chain", "status": market_health, "load_band": "high" if markets_rate is not None and markets_rate >= 60 else "medium" if markets_rate is not None and markets_rate > 0 else "idle", "activity_rate": markets_rate, "freshness_s": _fresh(feed_age)},
        {"id": "archive", "zone": "archive", "label": "Knowledge archive", "status": desk_status, "load_band": "medium" if archive_rate and archive_rate > 0 else "idle", "activity_rate": archive_rate, "freshness_s": _fresh(desk_age)},
    ]
    # Each link states what it measures and why the blanks are blank. A None here
    # is the finished answer, not a gap waiting for a default.
    links = [
        # Round trip from this host to the public edge. No request log for the
        # edge is readable from here, so its rate is genuinely unknown.
        {"source": "public-edge", "target": "orchestration", "status": desk_status, "latency_ms": link_latencies.get("public-edge:orchestration"), "event_rate": None, "signal_class": "network"},
        # Round trip to the compute tier the GPU gateway would route to. The
        # gateway is a streaming proxy that keeps no request log, so no rate.
        {"source": "orchestration", "target": "gpu-compute", "status": gpu_status, "latency_ms": link_latencies.get("orchestration:gpu-compute"), "event_rate": None, "signal_class": "agent"},
        # Agent events per minute from the presence spine. Nothing on this path
        # is an addressable endpoint, so there is no latency to measure.
        {"source": "gpu-compute", "target": "intelligence", "status": rh_status, "latency_ms": None, "event_rate": agent_rate, "signal_class": "agent"},
        # Both measured: the feed reports its own lag and its own message rate.
        {"source": "intelligence", "target": "markets", "status": market_health, "latency_ms": markets_latency_ms, "event_rate": markets_rate, "signal_class": "market"},
        # Rows per minute the last desk cycle wrote, while that cycle is still
        # current. A batch write path has no request latency.
        {"source": "intelligence", "target": "archive", "status": desk_status, "latency_ms": None, "event_rate": archive_rate, "signal_class": "archive"},
    ]

    events = presence_events + [
        {
            "id": f"agent-{agent['id']}",
            "observed_at": agent["updated_at"],
            "event_class": "agent",
            "source": "intelligence",
            "target": "archive",
            "label": f"{agent['role']} status observed",
            "status": "verified" if agent["verification"] == "verified" else "degraded",
        }
        for agent in agents[:8]
        if not presence_agents or agent not in presence_agents
    ]
    if markets_rate:
        events.append({"id": f"market-{int(now)}", "observed_at": observed_at, "event_class": "market", "source": "markets", "target": "intelligence", "label": "Market activity observed", "status": "observed"})
    if archive_rate:
        events.append({"id": f"archive-{int(now)}", "observed_at": observed_at, "event_class": "archive", "source": "intelligence", "target": "archive", "label": "Knowledge cycle recorded", "status": "verified"})

    degraded = any(node["status"] in {"degraded", "down"} for node in nodes)
    # Only the presence source describes task-executing agents. RH's historical
    # `agents` field contains monitored daemons and GPU services are processes;
    # both remain useful diagnostics above, but neither is active agent work.
    # The fleet count remains unknown unless every expected inventory source
    # arrived complete and the presence projection itself is error-free.
    active_agents_complete = (
        raw_presence_agents is not None
        and len(raw_presence_agents) <= 24
        and isinstance(rh_health.get("agents"), list)
        and len(raw_agents) <= 12
        and bool(gpu)
        and source_errors == 0
        and len(agents) <= 32
    )
    active_agents = (
        sum(
            1
            for agent in presence_agents
            if agent["state"] in {"working", "verifying"}
        )
        if active_agents_complete
        else None
    )
    agents = agents[:32]
    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": time.time_ns(),
        "summary": {
            "state": "degraded" if degraded else "observing",
            "active_agents": active_agents,
            "events_per_min": None,
            "verified_today": None,
            "attention": None,
        },
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": {
            "network": "Robinhood Chain",
            "status": market_status,
            "feed_age_s": feed_age if _epoch(feed.get("updated")) is not None else None,
            "events_per_min": markets_rate,
            "paper_strategies": paper_strategy_count,
            "decision_gate": "telegram",
            "execution": "off",
        },
        "events": events,
    }


def signed_headers(body: bytes, secret: str, *, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    if len(secret) < 32:
        raise ValueError("TELEMETRY_INGEST_SECRET must be at least 32 characters")
    ts = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_urlsafe(18)
    message = ts.encode() + b"." + nonce.encode() + b"." + body
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return {"Content-Type": "application/json", "X-Sapphire-Timestamp": ts, "X-Sapphire-Nonce": nonce, "X-Sapphire-Signature": signature}


def measure_latency_ms(endpoint: str, *, timeout: float = 2.0) -> float | None:
    """Measure one configured health endpoint without exposing its address."""
    return probes.http_latency_ms(endpoint, timeout=timeout)


def configured_latencies(
    *,
    http_probe: Callable[..., float | None] = probes.http_latency_ms,
    gateway_probe: Callable[..., float | None] = probes.gateway_route_latency_ms,
) -> dict[str, float | None]:
    """Measure the two link latencies this host can actually observe.

    The previous version read four `SAPPHIRE_*_PROBE` environment variables that
    were never set on any host, so `measure_latency_ms("")` returned None four
    times and every latency on the site was blank. The endpoints below are real
    and reachable, and the env vars still win where they are set.

    The other three Mac links are absent on purpose, not by oversight: nothing on
    those paths is an addressable endpoint to time. See the link table in
    `build_snapshot`.
    """
    return {
        "public-edge:orchestration": http_probe(
            os.getenv("SAPPHIRE_EDGE_PROBE") or PUBLIC_EDGE_HEALTH_URL
        ),
        "orchestration:gpu-compute": gateway_probe(
            os.getenv("SAPPHIRE_GPU_GATEWAY_PROBE") or GPU_GATEWAY_HEALTH_URL
        ),
    }


def _post(snapshot: dict[str, Any], *, endpoint: str, secret: str, timeout: float) -> dict[str, Any]:
    body = json.dumps(snapshot, separators=(",", ":"), allow_nan=False).encode()
    request = urllib.request.Request(endpoint, data=body, headers=signed_headers(body, secret), method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    return result if isinstance(result, dict) else {}


def push(
    snapshot: dict[str, Any],
    *,
    endpoint: str,
    secret: str,
    timeout: float = 10.0,
    transport: Callable[..., dict[str, Any]] = _post,
) -> dict[str, Any]:
    """Publish exactly one honest payload.

    A backend that still rejects null measurements must retain its last accepted
    snapshot until it is upgraded. Retrying with zero would turn "not measured"
    into "measured no traffic", which is fiction even when the old wire cannot
    express the distinction.
    """
    return transport(snapshot, endpoint=endpoint, secret=secret, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or publish a privacy-safe Sapphire Mission Snapshot")
    parser.add_argument("--push", action="store_true", help="submit to SAPPHIRE_TELEMETRY_ENDPOINT")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args()
    snapshot = build_snapshot(Sources.defaults(), link_latencies=configured_latencies())
    if args.push:
        endpoint = os.getenv("SAPPHIRE_TELEMETRY_ENDPOINT", "").strip()
        secret = os.getenv("TELEMETRY_INGEST_SECRET", "")
        if not endpoint:
            raise SystemExit("SAPPHIRE_TELEMETRY_ENDPOINT is required with --push")
        print(json.dumps(push(snapshot, endpoint=endpoint, secret=secret), sort_keys=True))
    else:
        print(json.dumps(snapshot, indent=None if args.compact else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

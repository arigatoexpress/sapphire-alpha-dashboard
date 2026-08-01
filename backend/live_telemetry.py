"""Signed, bounded telemetry ingest and public/operator projections.

The dashboard never accepts raw infrastructure dumps. Producers must submit the
small semantic schema below; unknown fields and attack-useful identifiers are
rejected before a snapshot enters the in-memory history.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import math
import os
import re
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Protocol


MAX_BODY_BYTES = 64 * 1024
MAX_REQUEST_SKEW_SECONDS = 300
# Paired with StartInterval in infra/com.sapphire.alpha-telemetry-publisher.plist:
# the publisher must fit two full cycles inside this window, or one missed push
# marks a healthy feed stale. Raising this number to silence a staleness report
# is the forbidden fix — a threshold that never fires reads green while checking
# nothing. Shorten the cadence instead. Enforced by test_machine_room_public.py.
DEFAULT_STALE_AFTER_SECONDS = 180
# The sovereign desk writes one explicitly versioned conjecture cycle per day.
# This TTL belongs to that source observation, not to the one-minute runtime
# heartbeat.  It is still re-evaluated on every read and withdrawn at expiry.
PUBLIC_RESEARCH_TTL_SECONDS = 24 * 60 * 60
# Public prose is code-owned, never copied from the private conjecture file or
# accepted as arbitrary signed producer text.  The internal opinion id is used
# only by the collector to select one fixed sentence and never enters the wire.
PUBLIC_RESEARCH_CLAIM_BY_ID = {
    "btc_bear_bottomed": (
        "Bitcoin has put in the cycle low for this bear/corrective phase"
    ),
}
PUBLIC_RESEARCH_STANCES = {"lean_no", "uncertain", "lean_yes"}
MAX_JSON_DEPTH = 64

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_WALLET_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\w)"
)
_HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,32}\b")
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

_FORBIDDEN_KEYS = re.compile(
    r"(?:host(?:name)?|endpoint|url|uri|path|port|pid|ip|token|secret|password|"
    r"credential|api[_-]?key|wallet|address|account|project[_-]?id|prompt|response|"
    r"balance|position|order[_-]?id)",
    re.IGNORECASE,
)

_FORBIDDEN_TEXT = (
    "http://",
    "https://",
    "ts.net",
    "/users/",
    "c:\\users",
    "localhost",
    "127.0.0.1",
)

_ZONES = {"edge", "orchestration", "compute", "intelligence", "markets", "archive"}
_HEALTH = {"healthy", "degraded", "down", "unknown"}
_LOAD = {"idle", "low", "medium", "high"}
_SUMMARY_STATES = {"observing", "quiet", "degraded", "offline"}
_SIGNAL_CLASSES = {"network", "agent", "market", "reliability", "archive"}
_AGENT_STATES = {"working", "verifying", "idle", "blocked", "offline"}
_VERIFICATION = {"verified", "pending", "failed", "not_applicable"}
_PROVIDERS = {"local GPU", "local CPU", "cloud reasoning", "hybrid", "rule-only", "unassigned"}
_MARKET_STATES = {"current", "delayed", "stale", "offline"}
_GATES = {"manual", "off", "unknown"}
_EXECUTION = {"off", "paper", "gated", "halted", "unknown"}
_EVENT_STATES = {"observed", "verified", "pending", "degraded", "failed", "recovered"}
_POSTURES = {"capital_preservation", "selective_risk", "risk_seeking", "neutral", "unknown"}
_LEADER_STATES = {"credible", "none", "unknown"}
_DESK_EXECUTION = {"halted", "off", "gated", "unknown"}
_LEDGER_STATES = {"reconciled", "unknown"}
_NEW_RISK_STATES = {"available", "restricted", "blocked", "unknown"}
_EXPERIMENT_STATES = {
    "collecting", "ready_for_terminal_evaluation", "complete", "invalidated", "unknown",
}
_COLLECTOR_STATES = {"current", "stale", "missing", "unknown"}
_TRACK_STATES = {"current", "stale", "inactive"}
_PUBLIC_STRATEGIES = {
    "flow-follow", "sniper", "equity", "rotation",
    "mean-rev", "smart-money", "breakout",
}


class TelemetryValidationError(ValueError):
    """Raised when a producer violates the semantic telemetry contract."""


def _require_bounded_structure(value: Any, *, max_depth: int = MAX_JSON_DEPTH) -> None:
    """Bound recursive semantic validation with an iterative preflight."""
    pending: list[tuple[Any, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > max_depth:
            raise TelemetryValidationError("telemetry JSON is too deeply nested")
        if isinstance(current, dict):
            pending.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            pending.extend((child, depth + 1) for child in current)


def _keys(value: Any, *, allowed: set[str], required: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TelemetryValidationError(f"{where} must be an object")
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        raise TelemetryValidationError(f"{where} has unsupported fields")
    if missing:
        raise TelemetryValidationError(f"{where} is missing required fields")
    return value


def _scan_forbidden(value: Any, *, where: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _FORBIDDEN_KEYS.search(str(key)):
                raise TelemetryValidationError(f"{where} contains a forbidden field")
            _scan_forbidden(child, where=f"{where}.{key}")
    elif isinstance(value, list):
        for child in value:
            _scan_forbidden(child, where=where)
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _FORBIDDEN_TEXT):
            raise TelemetryValidationError(f"{where} contains an internal identifier")
        if _IPV4_RE.search(value) or _WALLET_RE.search(value):
            raise TelemetryValidationError(f"{where} contains an internal identifier")
        if (
            _EMAIL_RE.search(value)
            or _PHONE_RE.search(value)
            or _HANDLE_RE.search(value)
            or _SSN_RE.search(value)
        ):
            raise TelemetryValidationError(f"{where} contains a personal identifier")


def _text(value: Any, *, where: str, limit: int = 120) -> str:
    if not isinstance(value, str):
        raise TelemetryValidationError(f"{where} must be text")
    value = " ".join(value.split()).strip()
    if not value or len(value) > limit:
        raise TelemetryValidationError(f"{where} has invalid length")
    _scan_forbidden(value, where=where)
    return value


def _enum(value: Any, allowed: set[str], *, where: str) -> str:
    value = _text(value, where=where, limit=40)
    if value not in allowed:
        raise TelemetryValidationError(f"{where} has an unsupported value")
    return value


def _number(value: Any, *, where: str, low: float = 0, high: float = 1_000_000) -> float:
    if isinstance(value, bool):
        raise TelemetryValidationError(f"{where} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TelemetryValidationError(f"{where} must be numeric") from exc
    if not math.isfinite(number) or not low <= number <= high:
        raise TelemetryValidationError(f"{where} is outside the allowed range")
    return round(number, 3)


def _integer(value: Any, *, where: str, low: int = 0, high: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise TelemetryValidationError(f"{where} must be an integer in range")
    return value


def _nullable_number(
    value: Any,
    *,
    where: str,
    low: float = 0,
    high: float = 1_000_000,
) -> float | None:
    if value is None:
        return None
    return _number(value, where=where, low=low, high=high)


def _nullable_integer(
    value: Any,
    *,
    where: str,
    low: int = 0,
    high: int = 1_000_000,
) -> int | None:
    if value is None:
        return None
    return _integer(value, where=where, low=low, high=high)


def _identifier(value: Any, *, where: str) -> str:
    value = _text(value, where=where, limit=40)
    if not _ID_RE.fullmatch(value):
        raise TelemetryValidationError(f"{where} must be a semantic identifier")
    return value


def _timestamp(value: Any, *, where: str, future_slack_s: int = 60) -> str:
    value = _text(value, where=where, limit=48)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TelemetryValidationError(f"{where} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise TelemetryValidationError(f"{where} must include a timezone")
    parsed = parsed.astimezone(UTC)
    if parsed.timestamp() > time.time() + future_slack_s:
        raise TelemetryValidationError(f"{where} is in the future")
    return parsed.isoformat()


def validate_research_projection(value: Any) -> dict[str, Any]:
    """Validate the complete public research allowlist.

    This intentionally is not a general conjecture schema.  It accepts one
    timestamp and four thesis fields; source ids, positions, instruments,
    accounts, prompts, evidence, falsifiers, and local provenance have no wire
    representation and therefore cannot leak through this boundary.
    """
    raw = _keys(
        value,
        allowed={"observed_at", "thesis"},
        required={"observed_at", "thesis"},
        where="research",
    )
    thesis = _keys(
        raw["thesis"],
        allowed={"claim", "stance", "probability", "horizon_days"},
        required={"claim", "stance", "probability", "horizon_days"},
        where="research.thesis",
    )
    claim = _text(thesis["claim"], where="research.thesis.claim", limit=280)
    if claim not in PUBLIC_RESEARCH_CLAIM_BY_ID.values():
        raise TelemetryValidationError("research.thesis.claim is not approved public copy")
    return {
        "observed_at": _timestamp(raw["observed_at"], where="research.observed_at"),
        "thesis": {
            "claim": claim,
            "stance": _enum(
                thesis["stance"],
                PUBLIC_RESEARCH_STANCES,
                where="research.thesis.stance",
            ),
            "probability": _number(
                thesis["probability"], where="research.thesis.probability", high=1),
            "horizon_days": _integer(
                thesis["horizon_days"],
                where="research.thesis.horizon_days",
                low=1,
                high=3650,
            ),
        },
    }


def _epistemics(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "updated_ts": None,
            "fresh": False,
            "thesis": None,
            "regime": {"label": "unknown", "fit": None, "data_quality": None, "drivers": []},
            "falsifiers": [],
            "learning": {
                "status": "unavailable", "open": None, "resolved": None,
                "mean_brier": None, "accuracy": None, "lessons": 0,
                "updated_ts": None,
            },
        }
    raw = _keys(
        value,
        allowed={"updated_ts", "fresh", "thesis", "regime", "falsifiers", "learning"},
        required={"updated_ts", "fresh", "thesis", "regime", "falsifiers", "learning"},
        where="desk.epistemics",
    )
    if not isinstance(raw["fresh"], bool):
        raise TelemetryValidationError("desk.epistemics.fresh must be boolean")
    thesis_raw = raw["thesis"]
    thesis = None
    if thesis_raw is not None:
        thesis_raw = _keys(
            thesis_raw,
            allowed={
                "id", "claim", "probability", "stance", "confidence",
                "data_quality", "horizon_days", "falsifier",
            },
            required={
                "id", "claim", "probability", "stance", "confidence",
                "data_quality", "horizon_days", "falsifier",
            },
            where="desk.epistemics.thesis",
        )
        thesis = {
            "id": _identifier(thesis_raw["id"], where="desk.epistemics.thesis.id"),
            "claim": _text(
                thesis_raw["claim"], where="desk.epistemics.thesis.claim", limit=280),
            "probability": _number(
                thesis_raw["probability"], where="desk.epistemics.thesis.probability",
                high=1),
            "stance": _text(
                thesis_raw["stance"], where="desk.epistemics.thesis.stance", limit=32),
            "confidence": _text(
                thesis_raw["confidence"], where="desk.epistemics.thesis.confidence",
                limit=32),
            "data_quality": _number(
                thesis_raw["data_quality"], where="desk.epistemics.thesis.data_quality",
                high=1),
            "horizon_days": _integer(
                thesis_raw["horizon_days"], where="desk.epistemics.thesis.horizon_days",
                low=1, high=3650),
            "falsifier": _text(
                thesis_raw["falsifier"], where="desk.epistemics.thesis.falsifier",
                limit=320),
        }
    regime_raw = _keys(
        raw["regime"],
        allowed={"label", "fit", "data_quality", "drivers"},
        required={"label", "fit", "data_quality", "drivers"},
        where="desk.epistemics.regime",
    )
    drivers_raw = regime_raw["drivers"]
    if not isinstance(drivers_raw, list) or len(drivers_raw) > 3:
        raise TelemetryValidationError("desk.epistemics.regime.drivers must be bounded")
    falsifiers_raw = raw["falsifiers"]
    if not isinstance(falsifiers_raw, list) or len(falsifiers_raw) > 5:
        raise TelemetryValidationError("desk.epistemics.falsifiers must be bounded")
    falsifiers = []
    for index, item in enumerate(falsifiers_raw):
        item = _keys(
            item,
            allowed={"claim_id", "condition", "status"},
            required={"claim_id", "condition", "status"},
            where=f"desk.epistemics.falsifiers[{index}]",
        )
        falsifiers.append({
            "claim_id": _identifier(
                item["claim_id"], where=f"desk.epistemics.falsifiers[{index}].claim_id"),
            "condition": _text(
                item["condition"], where=f"desk.epistemics.falsifiers[{index}].condition",
                limit=240),
            "status": _enum(
                item["status"], {"clear", "watch", "triggered", "unknown"},
                where=f"desk.epistemics.falsifiers[{index}].status"),
        })
    learning_raw = _keys(
        raw["learning"],
        allowed={
            "status", "open", "resolved", "mean_brier", "accuracy",
            "lessons", "updated_ts",
        },
        required={
            "status", "open", "resolved", "mean_brier", "accuracy",
            "lessons", "updated_ts",
        },
        where="desk.epistemics.learning",
    )
    return {
        "updated_ts": _nullable_number(
            raw["updated_ts"], where="desk.epistemics.updated_ts", high=4_102_444_800),
        "fresh": raw["fresh"],
        "thesis": thesis,
        "regime": {
            "label": _text(
                regime_raw["label"], where="desk.epistemics.regime.label", limit=40),
            "fit": _nullable_number(
                regime_raw["fit"], where="desk.epistemics.regime.fit", high=1),
            "data_quality": _nullable_number(
                regime_raw["data_quality"],
                where="desk.epistemics.regime.data_quality", high=1),
            "drivers": [
                _text(item, where=f"desk.epistemics.regime.drivers[{index}]", limit=160)
                for index, item in enumerate(drivers_raw)
            ],
        },
        "falsifiers": falsifiers,
        "learning": {
            "status": _enum(
                learning_raw["status"],
                {"bootstrapping", "learning", "unavailable"},
                where="desk.epistemics.learning.status",
            ),
            "open": _nullable_integer(
                learning_raw["open"], where="desk.epistemics.learning.open", high=10_000),
            "resolved": _nullable_integer(
                learning_raw["resolved"], where="desk.epistemics.learning.resolved",
                high=10_000),
            "mean_brier": _nullable_number(
                learning_raw["mean_brier"],
                where="desk.epistemics.learning.mean_brier", high=1),
            "accuracy": _nullable_number(
                learning_raw["accuracy"],
                where="desk.epistemics.learning.accuracy", high=1),
            "lessons": _integer(
                learning_raw["lessons"], where="desk.epistemics.learning.lessons",
                high=10_000),
            "updated_ts": _nullable_number(
                learning_raw["updated_ts"],
                where="desk.epistemics.learning.updated_ts", high=4_102_444_800),
        },
    }


def _autonomy(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "desired": "off", "active": False,
            "new_entries": "waiting", "reason": "not observed",
        }
    raw = _keys(
        value,
        allowed={"desired", "active", "new_entries", "reason"},
        required={"desired", "active", "new_entries", "reason"},
        where="desk.autonomy",
    )
    if not isinstance(raw["active"], bool):
        raise TelemetryValidationError("desk.autonomy.active must be boolean")
    return {
        "desired": _enum(raw["desired"], {"on", "off"}, where="desk.autonomy.desired"),
        "active": raw["active"],
        "new_entries": _enum(
            raw["new_entries"], {"available", "waiting"},
            where="desk.autonomy.new_entries",
        ),
        "reason": _text(raw["reason"], where="desk.autonomy.reason", limit=160),
    }


def _safety_floor(value: Any) -> dict[str, Any]:
    if value is None:
        return {
            "gate_valid": False, "pause_clear": None,
            "ledger": "unknown", "bounded_policy": False,
        }
    raw = _keys(
        value,
        allowed={"gate_valid", "pause_clear", "ledger", "bounded_policy"},
        required={"gate_valid", "pause_clear", "ledger", "bounded_policy"},
        where="desk.safety_floor",
    )
    for key in ("gate_valid", "bounded_policy"):
        if not isinstance(raw[key], bool):
            raise TelemetryValidationError(f"desk.safety_floor.{key} must be boolean")
    if raw["pause_clear"] is not None and not isinstance(raw["pause_clear"], bool):
        raise TelemetryValidationError(
            "desk.safety_floor.pause_clear must be boolean or null"
        )
    return {
        "gate_valid": raw["gate_valid"],
        "pause_clear": raw["pause_clear"],
        "ledger": _enum(
            raw["ledger"], _LEDGER_STATES, where="desk.safety_floor.ledger"),
        "bounded_policy": raw["bounded_policy"],
    }


def validate_snapshot(raw: Any) -> dict[str, Any]:
    """Return a normalized copy of the only telemetry shape we will store."""
    _require_bounded_structure(raw)
    _scan_forbidden(raw)
    obj = _keys(
        raw,
        allowed={
            "version",
            "observed_at",
            "sequence",
            "summary",
            "nodes",
            "links",
            "agents",
            "markets",
            "events",
            "desk",
            "research",
        },
        required={
            "version",
            "observed_at",
            "sequence",
            "summary",
            "nodes",
            "links",
            "agents",
            "markets",
            "events",
        },
        where="payload",
    )
    if obj["version"] != 1:
        raise TelemetryValidationError("unsupported telemetry version")
    observed_at = _timestamp(obj["observed_at"], where="observed_at")
    sequence = _integer(obj["sequence"], where="sequence", high=2**63 - 1)
    research = (
        validate_research_projection(obj["research"])
        if obj.get("research") is not None
        else None
    )
    if (
        research is not None
        and datetime.fromisoformat(research["observed_at"]).timestamp()
        > datetime.fromisoformat(observed_at).timestamp() + 0.001
    ):
        raise TelemetryValidationError("research observation is newer than its parent snapshot")

    desk_raw = obj.get("desk")
    if desk_raw is None or desk_raw == _empty_desk():
        desk = _empty_desk()
    else:
        desk_obj = _keys(
            desk_raw,
            allowed={
                "version", "updated_at", "posture", "leader", "validation",
                "decisions", "execution", "feeds", "tracks", "risk", "experiment",
                "epistemics", "autonomy", "safety_floor",
            },
            required={
                "version", "updated_at", "posture", "leader", "validation",
                "decisions", "execution", "feeds",
            },
            where="desk",
        )
        if desk_obj["version"] != 1:
            raise TelemetryValidationError("unsupported desk projection version")
        validation_raw = _keys(
            desk_obj["validation"],
            allowed={
                "oos_pass", "oos_total", "conflicts", "conflict_details",
                "replay_span_hours", "replay_data_through",
            },
            required={"oos_pass", "oos_total", "conflicts"},
            where="desk.validation",
        )
        conflict_details_raw = validation_raw.get("conflict_details", [])
        if not isinstance(conflict_details_raw, list) or len(conflict_details_raw) > 7:
            raise TelemetryValidationError(
                "desk.validation.conflict_details must be a bounded list"
            )
        conflict_details = []
        seen_conflict_strategies = set()
        for index, conflict_raw in enumerate(conflict_details_raw):
            conflict = _keys(
                conflict_raw,
                allowed={
                    "strategy", "live_return_pct", "replay_return_pct", "gap_pp",
                },
                required={
                    "strategy", "live_return_pct", "replay_return_pct", "gap_pp",
                },
                where=f"desk.validation.conflict_details[{index}]",
            )
            strategy = _enum(
                conflict["strategy"],
                _PUBLIC_STRATEGIES,
                where=f"desk.validation.conflict_details[{index}].strategy",
            )
            if strategy in seen_conflict_strategies:
                raise TelemetryValidationError(
                    "desk.validation.conflict_details repeats a strategy"
                )
            seen_conflict_strategies.add(strategy)
            conflict_details.append({
                "strategy": strategy,
                "live_return_pct": _number(
                    conflict["live_return_pct"],
                    where=f"desk.validation.conflict_details[{index}].live_return_pct",
                    low=-1_000,
                    high=10_000,
                ),
                "replay_return_pct": _number(
                    conflict["replay_return_pct"],
                    where=f"desk.validation.conflict_details[{index}].replay_return_pct",
                    low=-1_000,
                    high=10_000,
                ),
                "gap_pp": _number(
                    conflict["gap_pp"],
                    where=f"desk.validation.conflict_details[{index}].gap_pp",
                    low=0,
                    high=10_000,
                ),
            })
        conflicts = _integer(
            validation_raw["conflicts"],
            where="desk.validation.conflicts",
            high=100,
        )
        if (
            "conflict_details" in validation_raw
            and len(conflict_details) != conflicts
        ):
            raise TelemetryValidationError(
                "desk.validation.conflict_details must explain every conflict"
            )
        replay_data_through = validation_raw.get("replay_data_through")
        if replay_data_through is not None:
            replay_data_through = _text(
                replay_data_through,
                where="desk.validation.replay_data_through",
                limit=10,
            )
            try:
                if (
                    datetime.fromisoformat(replay_data_through).date().isoformat()
                    != replay_data_through
                ):
                    raise ValueError
            except ValueError as exc:
                raise TelemetryValidationError(
                    "desk.validation.replay_data_through must be an ISO date"
                ) from exc
        decisions_raw = _keys(
            desk_obj["decisions"],
            allowed={
                "pending",
                "pending_review",
                "approved_awaiting_execution",
                "eligible_execution",
                "blocked",
                "pending_policy_blocked",
            },
            required={"pending"},
            where="desk.decisions",
        )
        feeds_raw = _keys(
            desk_obj["feeds"],
            allowed={"fresh", "total"},
            required={"fresh", "total"},
            where="desk.feeds",
        )
        tracks_raw = desk_obj.get("tracks", [])
        if not isinstance(tracks_raw, list) or len(tracks_raw) > 7:
            raise TelemetryValidationError("desk.tracks must be a bounded list")
        public_tracks = []
        seen_tracks = set()
        for index, raw_track in enumerate(tracks_raw):
            track = _keys(
                raw_track,
                allowed={
                    "strategy", "status", "live_return_pct", "green_days",
                    "target_days", "open_count", "data_flags", "freshness_s",
                },
                required={
                    "strategy", "status", "live_return_pct", "green_days",
                    "target_days", "open_count", "data_flags", "freshness_s",
                },
                where=f"desk.tracks[{index}]",
            )
            strategy = _enum(
                track["strategy"],
                _PUBLIC_STRATEGIES,
                where=f"desk.tracks[{index}].strategy",
            )
            if strategy in seen_tracks:
                raise TelemetryValidationError("desk.tracks repeats a strategy")
            seen_tracks.add(strategy)
            green_days = _integer(
                track["green_days"],
                where=f"desk.tracks[{index}].green_days",
                high=100,
            )
            target_days = _integer(
                track["target_days"],
                where=f"desk.tracks[{index}].target_days",
                low=1,
                high=100,
            )
            if green_days > target_days:
                raise TelemetryValidationError(
                    "desk track green days exceed its target"
                )
            public_tracks.append({
                "strategy": strategy,
                "status": _enum(
                    track["status"],
                    _TRACK_STATES,
                    where=f"desk.tracks[{index}].status",
                ),
                "live_return_pct": _number(
                    track["live_return_pct"],
                    where=f"desk.tracks[{index}].live_return_pct",
                    low=-1_000,
                    high=10_000,
                ),
                "green_days": green_days,
                "target_days": target_days,
                "open_count": _integer(
                    track["open_count"],
                    where=f"desk.tracks[{index}].open_count",
                    high=1_000,
                ),
                "data_flags": _integer(
                    track["data_flags"],
                    where=f"desk.tracks[{index}].data_flags",
                    high=1_000,
                ),
                "freshness_s": _number(
                    track["freshness_s"],
                    where=f"desk.tracks[{index}].freshness_s",
                    high=31_536_000,
                ),
            })
        risk_raw = desk_obj.get("risk")
        if risk_raw is None:
            risk_raw = {
                "ledger_state": "unknown",
                "realized_drawdown_pct": None,
                "drawdown_limit_pct": None,
                "budget_remaining_pct": None,
                "new_risk": "unknown",
            }
        risk_raw = _keys(
            risk_raw,
            allowed={
                "ledger_state", "realized_drawdown_pct", "drawdown_limit_pct",
                "budget_remaining_pct", "new_risk",
            },
            required={
                "ledger_state", "realized_drawdown_pct", "drawdown_limit_pct",
                "budget_remaining_pct", "new_risk",
            },
            where="desk.risk",
        )
        experiment_raw = desk_obj.get("experiment")
        if experiment_raw is None:
            experiment_raw = {
                "status": "unknown",
                "qualified_days": None,
                "required_days": None,
                "last_committed_date": None,
                "collector": "unknown",
            }
        experiment_raw = _keys(
            experiment_raw,
            allowed={
                "status", "qualified_days", "required_days",
                "last_committed_date", "collector",
            },
            required={
                "status", "qualified_days", "required_days",
                "last_committed_date", "collector",
            },
            where="desk.experiment",
        )
        last_committed_date = experiment_raw["last_committed_date"]
        if last_committed_date is not None:
            last_committed_date = _text(
                last_committed_date,
                where="desk.experiment.last_committed_date",
                limit=10,
            )
            try:
                if datetime.fromisoformat(last_committed_date).date().isoformat() != last_committed_date:
                    raise ValueError
            except ValueError as exc:
                raise TelemetryValidationError(
                    "desk.experiment.last_committed_date must be an ISO date"
                ) from exc
        desk = {
            "version": 1,
            "updated_at": _timestamp(desk_obj["updated_at"], where="desk.updated_at"),
            "posture": _enum(desk_obj["posture"], _POSTURES, where="desk.posture"),
            "leader": _enum(desk_obj["leader"], _LEADER_STATES, where="desk.leader"),
            "validation": {
                "oos_pass": _integer(validation_raw["oos_pass"], where="desk.validation.oos_pass", high=100),
                "oos_total": _integer(validation_raw["oos_total"], where="desk.validation.oos_total", high=100),
                "conflicts": conflicts,
                "conflict_details": conflict_details,
                "replay_span_hours": _nullable_number(
                    validation_raw.get("replay_span_hours"),
                    where="desk.validation.replay_span_hours",
                    high=100_000,
                ),
                "replay_data_through": replay_data_through,
            },
            "decisions": {
                "pending": _nullable_integer(
                    decisions_raw["pending"],
                    where="desk.decisions.pending",
                    high=1_000,
                ),
                "pending_review": _nullable_integer(
                    decisions_raw.get("pending_review"),
                    where="desk.decisions.pending_review",
                    high=1_000,
                ),
                "approved_awaiting_execution": _nullable_integer(
                    decisions_raw.get("approved_awaiting_execution"),
                    where="desk.decisions.approved_awaiting_execution",
                    high=1_000,
                ),
                "eligible_execution": _nullable_integer(
                    decisions_raw.get("eligible_execution"),
                    where="desk.decisions.eligible_execution",
                    high=1_000,
                ),
                "blocked": _nullable_integer(
                    decisions_raw.get("blocked"),
                    where="desk.decisions.blocked",
                    high=1_000,
                ),
                "pending_policy_blocked": _nullable_integer(
                    decisions_raw.get("pending_policy_blocked"),
                    where="desk.decisions.pending_policy_blocked",
                    high=1_000,
                ),
            },
            "execution": _enum(desk_obj["execution"], _DESK_EXECUTION, where="desk.execution"),
            "feeds": {
                "fresh": _integer(feeds_raw["fresh"], where="desk.feeds.fresh", high=100),
                "total": _integer(feeds_raw["total"], where="desk.feeds.total", high=100),
            },
            "tracks": public_tracks,
            "risk": {
                "ledger_state": _enum(
                    risk_raw["ledger_state"],
                    _LEDGER_STATES,
                    where="desk.risk.ledger_state",
                ),
                "realized_drawdown_pct": _nullable_number(
                    risk_raw["realized_drawdown_pct"],
                    where="desk.risk.realized_drawdown_pct",
                    high=100,
                ),
                "drawdown_limit_pct": _nullable_number(
                    risk_raw["drawdown_limit_pct"],
                    where="desk.risk.drawdown_limit_pct",
                    high=100,
                ),
                "budget_remaining_pct": _nullable_number(
                    risk_raw["budget_remaining_pct"],
                    where="desk.risk.budget_remaining_pct",
                    high=100,
                ),
                "new_risk": _enum(
                    risk_raw["new_risk"],
                    _NEW_RISK_STATES,
                    where="desk.risk.new_risk",
                ),
            },
            "experiment": {
                "status": _enum(
                    experiment_raw["status"],
                    _EXPERIMENT_STATES,
                    where="desk.experiment.status",
                ),
                "qualified_days": _nullable_integer(
                    experiment_raw["qualified_days"],
                    where="desk.experiment.qualified_days",
                    high=100,
                ),
                "required_days": _nullable_integer(
                    experiment_raw["required_days"],
                    where="desk.experiment.required_days",
                    high=100,
                ),
                "last_committed_date": last_committed_date,
                "collector": _enum(
                    experiment_raw["collector"],
                    _COLLECTOR_STATES,
                    where="desk.experiment.collector",
                ),
            },
            "epistemics": _epistemics(desk_obj.get("epistemics")),
            "autonomy": _autonomy(desk_obj.get("autonomy")),
            "safety_floor": _safety_floor(desk_obj.get("safety_floor")),
        }
        if desk["validation"]["oos_pass"] > desk["validation"]["oos_total"]:
            raise TelemetryValidationError("desk OOS passing count exceeds total")
        if desk["feeds"]["fresh"] > desk["feeds"]["total"]:
            raise TelemetryValidationError("desk fresh feed count exceeds total")
        decision_counts = desk["decisions"]
        if (
            decision_counts["pending_review"] is not None
            and decision_counts["pending_policy_blocked"] is not None
            and decision_counts["pending"] != (
                decision_counts["pending_review"]
                + decision_counts["pending_policy_blocked"]
            )
        ):
            raise TelemetryValidationError("desk pending decision counts disagree")
        if all(
            decision_counts[key] is not None
            for key in (
                "approved_awaiting_execution",
                "eligible_execution",
                "blocked",
            )
        ) and (
            decision_counts["eligible_execution"] + decision_counts["blocked"]
            != decision_counts["approved_awaiting_execution"]
        ):
            raise TelemetryValidationError("desk execution queue counts disagree")
        risk = desk["risk"]
        risk_numbers = (
            risk["realized_drawdown_pct"],
            risk["drawdown_limit_pct"],
            risk["budget_remaining_pct"],
        )
        if risk["ledger_state"] == "reconciled" and (
            any(value is None for value in risk_numbers)
            or risk["new_risk"] == "unknown"
        ):
            raise TelemetryValidationError("desk reconciled risk state is incomplete")
        if risk["ledger_state"] == "unknown" and (
            any(value is not None for value in risk_numbers)
            or risk["new_risk"] != "unknown"
        ):
            raise TelemetryValidationError("desk unknown risk state carries conclusions")
        experiment = desk["experiment"]
        if experiment["status"] == "unknown":
            if (
                experiment["qualified_days"] is not None
                or experiment["required_days"] is not None
                or experiment["last_committed_date"] is not None
                or experiment["collector"] != "unknown"
            ):
                raise TelemetryValidationError("desk unknown experiment carries conclusions")
        elif (
            experiment["qualified_days"] is None
            or experiment["required_days"] is None
            or experiment["qualified_days"] > experiment["required_days"]
        ):
            raise TelemetryValidationError("desk experiment day counts are invalid")

    summary_raw = _keys(
        obj["summary"],
        allowed={"state", "active_agents", "events_per_min", "verified_today", "attention"},
        required={"state", "active_agents", "events_per_min", "verified_today", "attention"},
        where="summary",
    )
    summary = {
        "state": _enum(summary_raw["state"], _SUMMARY_STATES, where="summary.state"),
        "active_agents": None
        if summary_raw["active_agents"] is None
        else _integer(summary_raw["active_agents"], where="summary.active_agents", high=100),
        "events_per_min": None
        if summary_raw["events_per_min"] is None
        else _number(summary_raw["events_per_min"], where="summary.events_per_min"),
        "verified_today": None
        if summary_raw["verified_today"] is None
        else _integer(summary_raw["verified_today"], where="summary.verified_today"),
        "attention": None
        if summary_raw["attention"] is None
        else _integer(summary_raw["attention"], where="summary.attention", high=100),
    }

    if not isinstance(obj["nodes"], list) or len(obj["nodes"]) > 24:
        raise TelemetryValidationError("nodes must be a bounded list")
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, raw_node in enumerate(obj["nodes"]):
        # `load` was called `load_band` before the redaction tier was deleted. It
        # was never a band: producers measure a categorical load directly.
        #
        # The wire name is deliberately still `load_band`, and the collectors in
        # telemetry/ still send it. Ingest and deploy are decoupled in time: the
        # publisher runs from this checkout every 60 s while the backend only
        # changes on a gated deploy, so a producer that switched first would 422
        # against the live service until Ari deploys — which is exactly what
        # happened when this rename was attempted producer-first. Renaming the
        # wire field is a follow-up for after the deploy lands; until then this
        # alias absorbs it and nothing downstream ever sees the old name.
        if isinstance(raw_node, dict) and "load_band" in raw_node and "load" not in raw_node:
            raw_node = {
                ("load" if key == "load_band" else key): value for key, value in raw_node.items()
            }
        node = _keys(
            raw_node,
            allowed={"id", "zone", "label", "status", "load", "activity_rate", "freshness_s"},
            required={"id", "zone", "label", "status", "load", "activity_rate", "freshness_s"},
            where=f"nodes[{index}]",
        )
        node_id = _identifier(node["id"], where=f"nodes[{index}].id")
        if node_id in node_ids:
            raise TelemetryValidationError("node ids must be unique")
        node_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "zone": _enum(node["zone"], _ZONES, where=f"nodes[{index}].zone"),
                "label": _text(node["label"], where=f"nodes[{index}].label", limit=64),
                "status": _enum(node["status"], _HEALTH, where=f"nodes[{index}].status"),
                "load": _enum(node["load"], _LOAD, where=f"nodes[{index}].load"),
                "activity_rate": None
                if node["activity_rate"] is None
                else _number(node["activity_rate"], where=f"nodes[{index}].activity_rate"),
                "freshness_s": _number(node["freshness_s"], where=f"nodes[{index}].freshness_s", high=86_400),
            }
        )

    if not isinstance(obj["links"], list) or len(obj["links"]) > 48:
        raise TelemetryValidationError("links must be a bounded list")
    links: list[dict[str, Any]] = []
    for index, raw_link in enumerate(obj["links"]):
        link = _keys(
            raw_link,
            allowed={"source", "target", "status", "latency_ms", "event_rate", "signal_class"},
            required={"source", "target", "status", "latency_ms", "event_rate", "signal_class"},
            where=f"links[{index}]",
        )
        source = _identifier(link["source"], where=f"links[{index}].source")
        target = _identifier(link["target"], where=f"links[{index}].target")
        if source not in node_ids or target not in node_ids or source == target:
            raise TelemetryValidationError("links must connect distinct declared nodes")
        links.append(
            {
                "source": source,
                "target": target,
                "status": _enum(link["status"], _HEALTH, where=f"links[{index}].status"),
                "latency_ms": None
                if link["latency_ms"] is None
                else _number(link["latency_ms"], where=f"links[{index}].latency_ms", high=60_000),
                # None means "not measured", exactly as it does for latency_ms
                # above, and it must survive to the client unchanged. Coercing it
                # to 0 here would publish "no traffic on this edge" as a
                # measurement, which is the one failure mode a transparency site
                # cannot afford: a fabricated number is indistinguishable from an
                # observed one once it is on the wire.
                "event_rate": None
                if link["event_rate"] is None
                else _number(link["event_rate"], where=f"links[{index}].event_rate"),
                "signal_class": _enum(
                    link["signal_class"], _SIGNAL_CLASSES, where=f"links[{index}].signal_class"
                ),
            }
        )

    if not isinstance(obj["agents"], list) or len(obj["agents"]) > 32:
        raise TelemetryValidationError("agents must be a bounded list")
    agents: list[dict[str, Any]] = []
    agent_ids: set[str] = set()
    for index, raw_agent in enumerate(obj["agents"]):
        agent = _keys(
            raw_agent,
            allowed={"id", "role", "state", "activity", "verification", "provider_class", "updated_at"},
            required={"id", "role", "state", "activity", "verification", "provider_class", "updated_at"},
            where=f"agents[{index}]",
        )
        agent_id = _identifier(agent["id"], where=f"agents[{index}].id")
        if agent_id in agent_ids:
            raise TelemetryValidationError("agent ids must be unique")
        agent_ids.add(agent_id)
        agents.append(
            {
                "id": agent_id,
                "role": _text(agent["role"], where=f"agents[{index}].role", limit=64),
                "state": _enum(agent["state"], _AGENT_STATES, where=f"agents[{index}].state"),
                "activity": _text(agent["activity"], where=f"agents[{index}].activity", limit=120),
                "verification": _enum(
                    agent["verification"], _VERIFICATION, where=f"agents[{index}].verification"
                ),
                "provider_class": _enum(
                    agent["provider_class"], _PROVIDERS, where=f"agents[{index}].provider_class"
                ),
                "updated_at": _timestamp(agent["updated_at"], where=f"agents[{index}].updated_at"),
            }
        )

    market = _keys(
        obj["markets"],
        allowed={
            "network",
            "status",
            "feed_age_s",
            "events_per_min",
            "paper_strategies",
            "decision_gate",
            "execution",
        },
        required={
            "network",
            "status",
            "feed_age_s",
            "events_per_min",
            "paper_strategies",
            "decision_gate",
            "execution",
        },
        where="markets",
    )
    markets = {
        "network": _text(market["network"], where="markets.network", limit=48),
        "status": _enum(market["status"], _MARKET_STATES, where="markets.status"),
        "feed_age_s": None
        if market["feed_age_s"] is None
        else _number(market["feed_age_s"], where="markets.feed_age_s", high=86_400),
        "events_per_min": None
        if market["events_per_min"] is None
        else _number(market["events_per_min"], where="markets.events_per_min"),
        "paper_strategies": None
        if market["paper_strategies"] is None
        else _integer(market["paper_strategies"], where="markets.paper_strategies", high=100),
        "decision_gate": _enum(market["decision_gate"], _GATES, where="markets.decision_gate"),
        "execution": _enum(market["execution"], _EXECUTION, where="markets.execution"),
    }

    if not isinstance(obj["events"], list) or len(obj["events"]) > 100:
        raise TelemetryValidationError("events must be a bounded list")
    events: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    for index, raw_event in enumerate(obj["events"]):
        event = _keys(
            raw_event,
            allowed={"id", "observed_at", "event_class", "source", "target", "label", "status"},
            required={"id", "observed_at", "event_class", "source", "target", "label", "status"},
            where=f"events[{index}]",
        )
        event_id = _identifier(event["id"], where=f"events[{index}].id")
        if event_id in event_ids:
            raise TelemetryValidationError("event ids must be unique")
        event_ids.add(event_id)
        events.append(
            {
                "id": event_id,
                "observed_at": _timestamp(event["observed_at"], where=f"events[{index}].observed_at"),
                "event_class": _enum(
                    event["event_class"], _SIGNAL_CLASSES, where=f"events[{index}].event_class"
                ),
                "source": _enum(event["source"], _ZONES, where=f"events[{index}].source"),
                "target": _enum(event["target"], _ZONES, where=f"events[{index}].target"),
                "label": _text(event["label"], where=f"events[{index}].label", limit=120),
                "status": _enum(event["status"], _EVENT_STATES, where=f"events[{index}].status"),
            }
        )

    normalized = {
        "version": 1,
        "observed_at": observed_at,
        "sequence": sequence,
        "summary": summary,
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": markets,
        "events": events,
        "desk": desk,
    }
    if research is not None:
        normalized["research"] = research
    return normalized


def _empty_desk() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": None,
        "posture": "unknown",
        "leader": "unknown",
        "validation": {
            "oos_pass": None,
            "oos_total": None,
            "conflicts": None,
            "conflict_details": [],
            "replay_span_hours": None,
            "replay_data_through": None,
        },
        "decisions": {
            "pending": None,
            "pending_review": None,
            "approved_awaiting_execution": None,
            "eligible_execution": None,
            "blocked": None,
            "pending_policy_blocked": None,
        },
        "execution": "unknown",
        "feeds": {"fresh": None, "total": None},
        "tracks": [],
        "risk": {
            "ledger_state": "unknown",
            "realized_drawdown_pct": None,
            "drawdown_limit_pct": None,
            "budget_remaining_pct": None,
            "new_risk": "unknown",
        },
        "experiment": {
            "status": "unknown",
            "qualified_days": None,
            "required_days": None,
            "last_committed_date": None,
            "collector": "unknown",
        },
        "epistemics": _epistemics(None),
        "autonomy": _autonomy(None),
        "safety_floor": _safety_floor(None),
    }


def _normalize_stored(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Bring a stored snapshot onto the current schema before serving it.

    Snapshots written before the redaction tier was deleted are already sitting
    in Firestore with `load_band` on each node. They are served unchanged on the
    next read, so without this the "no `*_band` key anywhere" guarantee would
    hold for fresh pushes and quietly fail for everything already persisted.
    """
    for node in snapshot.get("nodes", []):
        if isinstance(node, dict) and "load_band" in node:
            node.setdefault("load", node.pop("load_band"))
            node.pop("load_band", None)
    empty_desk = _empty_desk()
    desk = snapshot.setdefault("desk", empty_desk)
    if isinstance(desk, dict):
        for key in ("epistemics", "autonomy", "safety_floor"):
            desk.setdefault(key, empty_desk[key])
        safety = desk.get("safety_floor")
        if isinstance(safety, dict):
            safety.setdefault("pause_clear", None)
    markets = snapshot.get("markets")
    if isinstance(markets, dict):
        # Telegram callbacks are retired.  Old durable snapshots may still
        # contain the former enum, but read-time compatibility must not revive
        # it as an execution gate.
        if markets.get("decision_gate") == "telegram":
            markets["decision_gate"] = "unknown"
    return snapshot


def _age_seconds(now: float, value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    age = now - parsed.timestamp()
    return age if age >= 0 else None


def _timestamp_epoch(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.timestamp() if parsed.tzinfo is not None else None


def _epoch_age_seconds(now: float, value: Any) -> float | None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        return None
    age = now - float(value)
    return age if age >= 0 else None


def _expire_desk_runtime(desk: dict[str, Any]) -> None:
    """Withdraw control-plane claims while retaining their persisted timestamp."""
    desk["posture"] = "unknown"
    desk["leader"] = "unknown"
    validation = desk.get("validation")
    if isinstance(validation, dict):
        validation.update(
            {
                "oos_pass": None,
                "oos_total": None,
                "conflicts": None,
                "conflict_details": [],
                "replay_span_hours": None,
                "replay_data_through": None,
            }
        )
    decisions = desk.get("decisions")
    if isinstance(decisions, dict):
        for key in tuple(decisions):
            decisions[key] = None
    desk["execution"] = "unknown"
    desk["feeds"] = {"fresh": None, "total": None}
    desk["tracks"] = []
    desk["autonomy"] = _autonomy(None)
    desk["safety_floor"] = _safety_floor(None)
    risk = desk.get("risk")
    if isinstance(risk, dict):
        risk.update(
            {
                "ledger_state": "unknown",
                "realized_drawdown_pct": None,
                "drawdown_limit_pct": None,
                "budget_remaining_pct": None,
                "new_risk": "unknown",
            }
        )
    experiment = desk.get("experiment")
    if isinstance(experiment, dict):
        experiment.update(
            {
                "status": "unknown",
                "qualified_days": None,
                "required_days": None,
                "last_committed_date": None,
                "collector": "unknown",
            }
        )
    desk["epistemics"] = _epistemics(None)


def _age_runtime_projection(
    snapshot: dict[str, Any],
    *,
    now: float,
    snapshot_observed_at: float,
    stale_after_seconds: float,
) -> None:
    """Age relative fields from persisted observations and fail closed.

    Producers persist relative ages at ``observed_at``.  Returning those same
    numbers on every request made an hours-old snapshot look like a one-second
    market feed.  This projection only adds elapsed time; it never edits the
    stored snapshot or replaces a source timestamp with request time.
    """
    # A tenth of a second is far below every declared TTL and keeps two
    # back-to-back readers on the same semantic projection.
    elapsed = round(max(0.0, now - snapshot_observed_at), 1)
    parent_current = elapsed <= stale_after_seconds

    for node in snapshot.get("nodes", []):
        if not isinstance(node, dict):
            continue
        age = node.get("freshness_s")
        if isinstance(age, (int, float)) and not isinstance(age, bool):
            age = round(max(0.0, float(age)) + elapsed, 3)
            node["freshness_s"] = age
            if not parent_current or age > stale_after_seconds:
                node["status"] = "unknown"
                node["activity_rate"] = None

    for link in snapshot.get("links", []):
        if isinstance(link, dict) and not parent_current:
            link["status"] = "unknown"
            link["event_rate"] = None

    agents = snapshot.get("agents")
    expired_agent = not isinstance(agents, list)
    projected_agents: list[dict[str, Any]] = []
    for agent in agents if isinstance(agents, list) else []:
        if not isinstance(agent, dict):
            expired_agent = True
            continue
        updated_epoch = _timestamp_epoch(agent.get("updated_at"))
        age = _age_seconds(now, agent.get("updated_at"))
        if (
            not parent_current
            or updated_epoch is None
            or updated_epoch > snapshot_observed_at
            or age is None
            or age > stale_after_seconds
        ):
            expired_agent = True
            agent["state"] = "offline"
            agent["verification"] = "pending"
            agent["activity"] = "Capability observation unavailable"
        projected_agents.append(agent)
    snapshot["agents"] = projected_agents

    events = snapshot.get("events")
    projected_events: list[dict[str, Any]] = []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        event_epoch = _timestamp_epoch(event.get("observed_at"))
        event_age = _age_seconds(now, event.get("observed_at"))
        if (
            parent_current
            and event_epoch is not None
            and event_epoch <= snapshot_observed_at
            and event_age is not None
            and event_age <= stale_after_seconds
        ):
            projected_events.append(event)
    snapshot["events"] = projected_events

    markets = snapshot.get("markets")
    if isinstance(markets, dict):
        feed_age = markets.get("feed_age_s")
        if isinstance(feed_age, (int, float)) and not isinstance(feed_age, bool):
            feed_age = round(max(0.0, float(feed_age)) + elapsed, 3)
            markets["feed_age_s"] = feed_age
            markets["status"] = (
                "current"
                if feed_age <= 60
                else "delayed"
                if feed_age <= 300
                else "stale"
            )
        else:
            markets["status"] = "offline"
        if not parent_current:
            markets["status"] = (
                "stale" if markets.get("feed_age_s") is not None else "offline"
            )
        if not parent_current or markets["status"] not in {"current", "delayed"}:
            markets["events_per_min"] = None
            markets["decision_gate"] = "unknown"
            markets["execution"] = "unknown"

    desk = snapshot.get("desk")
    if isinstance(desk, dict):
        desk_epoch = _timestamp_epoch(desk.get("updated_at"))
        desk_age = _age_seconds(now, desk.get("updated_at"))
        if (
            not parent_current
            or desk_epoch is None
            or desk_epoch > snapshot_observed_at
            or desk_age is None
            or desk_age > stale_after_seconds
        ):
            _expire_desk_runtime(desk)
        current_tracks: list[dict[str, Any]] = []
        for track in desk.get("tracks", []):
            if not isinstance(track, dict):
                continue
            age = track.get("freshness_s")
            if isinstance(age, (int, float)) and not isinstance(age, bool):
                track["freshness_s"] = round(max(0.0, float(age)) + elapsed, 3)
                if parent_current and track["freshness_s"] <= stale_after_seconds:
                    current_tracks.append(track)
        desk["tracks"] = current_tracks
        epistemics = desk.get("epistemics")
        if isinstance(epistemics, dict):
            epistemic_age = _epoch_age_seconds(now, epistemics.get("updated_ts"))
            learning = epistemics.get("learning")
            learning_age = (
                _epoch_age_seconds(now, learning.get("updated_ts"))
                if isinstance(learning, dict)
                else None
            )
            if (
                epistemics.get("fresh") is not True
                or (
                    isinstance(epistemics.get("updated_ts"), (int, float))
                    and float(epistemics["updated_ts"]) > snapshot_observed_at + 0.001
                )
                or (
                    isinstance(learning, dict)
                    and isinstance(learning.get("updated_ts"), (int, float))
                    and float(learning["updated_ts"]) > snapshot_observed_at + 0.001
                )
                or epistemic_age is None
                or epistemic_age > stale_after_seconds
                or learning_age is None
                or learning_age > stale_after_seconds
            ):
                desk["epistemics"] = _epistemics(None)

    research = snapshot.get("research")
    if isinstance(research, dict):
        research_epoch = _timestamp_epoch(research.get("observed_at"))
        research_age = _age_seconds(now, research.get("observed_at"))
        if (
            not parent_current
            or research_epoch is None
            or research_epoch > snapshot_observed_at + 0.001
            or research_age is None
            or research_age > PUBLIC_RESEARCH_TTL_SECONDS
        ):
            snapshot.pop("research", None)

    summary = snapshot.get("summary")
    if isinstance(summary, dict):
        if not parent_current:
            summary.update(
                {
                    "state": "degraded",
                    "active_agents": None,
                    "events_per_min": None,
                    "attention": None,
                }
            )
        elif expired_agent:
            summary["state"] = "degraded"
            summary["active_agents"] = None
        else:
            reported_active = summary.get("active_agents")
            derived_active = sum(
                agent.get("state") in {"working", "verifying"}
                for agent in projected_agents
            )
            if (
                reported_active is not None
                and (
                    type(reported_active) is not int
                    or reported_active != derived_active
                )
            ):
                summary["state"] = "degraded"
                summary["active_agents"] = None


def _empty_snapshot(*, status: str = "offline") -> dict[str, Any]:
    """The honest shape when nothing has been observed. One shape for everyone."""
    return {
        "version": 1,
        "observed_at": None,
        "sequence": None,
        "summary": {
            "state": "not observed",
            "active_agents": None,
            "events_per_min": None,
            "verified_today": None,
            "attention": None,
        },
        "nodes": [],
        "links": [],
        "agents": [],
        "markets": {
            "network": "Robinhood Chain",
            "status": "offline",
            "feed_age_s": None,
            "events_per_min": None,
            "paper_strategies": None,
            "decision_gate": "unknown",
            "execution": "unknown",
        },
        "events": [],
        "desk": _empty_desk(),
        "status": status,
        "freshness_s": None,
        "served_at": datetime.now(UTC).isoformat(),
    }


class TelemetryPersistence(Protocol):
    """Instance-independent storage boundary for accepted semantic snapshots."""

    def accept(self, snapshot: dict[str, Any], *, nonce: str, received_at: float) -> None: ...

    def select(self, *, received_before: float) -> tuple[float, dict[str, Any]] | None: ...

    def has_history(self) -> bool: ...

    def reset(self) -> None: ...


class MemoryTelemetryPersistence:
    """Deterministic local/test backend. Production uses Firestore."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: deque[tuple[float, dict[str, Any]]] = deque(maxlen=240)
        self._nonces: dict[str, float] = {}

    def accept(self, snapshot: dict[str, Any], *, nonce: str, received_at: float) -> None:
        with self._lock:
            self._nonces = {
                saved_nonce: seen_at
                for saved_nonce, seen_at in self._nonces.items()
                if received_at - seen_at <= MAX_REQUEST_SKEW_SECONDS
            }
            if nonce in self._nonces:
                raise FileExistsError("telemetry nonce already used")
            if self._history and snapshot["sequence"] <= self._history[-1][1]["sequence"]:
                raise TelemetryValidationError("telemetry sequence must increase")
            self._nonces[nonce] = received_at
            self._history.append((received_at, copy.deepcopy(snapshot)))

    def select(self, *, received_before: float) -> tuple[float, dict[str, Any]] | None:
        with self._lock:
            for received_at, snapshot in reversed(self._history):
                if received_at <= received_before:
                    return received_at, copy.deepcopy(snapshot)
        return None

    def has_history(self) -> bool:
        with self._lock:
            return bool(self._history)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._nonces.clear()


class FirestoreTelemetryPersistence:
    """Atomic latest/history store shared by every Cloud Run instance.

    Imports the Google client lazily so local development and tests do not need
    cloud credentials. Nonce and sequence checks live in the same transaction as
    the snapshot write, preventing cross-instance replay or reordering.
    """

    def __init__(self, *, collection: str, database: str | None = None) -> None:
        try:
            from google.cloud import firestore
        except ImportError as exc:  # pragma: no cover - production dependency check
            raise RuntimeError("Firestore telemetry storage is unavailable") from exc
        self._firestore = firestore
        self._client = firestore.Client(database=database or "(default)")
        self._root = self._client.collection(collection)
        self._latest = self._root.document("latest")
        self._history = self._root.document("state").collection("history")
        self._nonces = self._root.document("state").collection("nonces")

    def accept(self, snapshot: dict[str, Any], *, nonce: str, received_at: float) -> None:
        nonce_id = hashlib.sha256(nonce.encode()).hexdigest()
        nonce_ref = self._nonces.document(nonce_id)
        history_ref = self._history.document(f"{snapshot['sequence']:020d}")
        transaction = self._client.transaction()
        firestore = self._firestore

        @firestore.transactional
        def commit(txn: Any) -> None:
            latest = self._latest.get(transaction=txn)
            used_nonce = nonce_ref.get(transaction=txn)
            if used_nonce.exists:
                raise FileExistsError("telemetry nonce already used")
            if latest.exists:
                previous = latest.to_dict() or {}
                if snapshot["sequence"] <= int(previous.get("sequence", -1)):
                    raise TelemetryValidationError("telemetry sequence must increase")
            record = {
                "sequence": snapshot["sequence"],
                "received_at": received_at,
                "snapshot": copy.deepcopy(snapshot),
            }
            txn.set(self._latest, record)
            txn.set(history_ref, record)
            txn.set(
                nonce_ref,
                {
                    "seen_at": datetime.fromtimestamp(received_at, UTC),
                    "expires_at": datetime.fromtimestamp(received_at, UTC)
                    + timedelta(seconds=MAX_REQUEST_SKEW_SECONDS * 2),
                },
            )

        try:
            commit(transaction)
        except (FileExistsError, TelemetryValidationError):
            raise
        except Exception as exc:  # pragma: no cover - cloud failure surface
            raise RuntimeError("durable telemetry write failed") from exc

    @staticmethod
    def _decode(document: Any) -> tuple[float, dict[str, Any]] | None:
        if document is None or not document.exists:
            return None
        record = document.to_dict() or {}
        snapshot = record.get("snapshot")
        received_at = record.get("received_at")
        if not isinstance(snapshot, dict) or not isinstance(received_at, (int, float)):
            return None
        return float(received_at), snapshot

    def select(self, *, received_before: float) -> tuple[float, dict[str, Any]] | None:
        try:
            latest = self._decode(self._latest.get())
            if latest and latest[0] <= received_before:
                return latest
            query = (
                self._history.where(
                    filter=self._firestore.FieldFilter("received_at", "<=", received_before)
                )
                .order_by("received_at", direction=self._firestore.Query.DESCENDING)
                .limit(1)
            )
            rows = list(query.stream())
            return self._decode(rows[0]) if rows else None
        except Exception as exc:  # pragma: no cover - cloud failure surface
            raise RuntimeError("durable telemetry read failed") from exc

    def has_history(self) -> bool:
        try:
            return self._latest.get().exists
        except Exception as exc:  # pragma: no cover - cloud failure surface
            raise RuntimeError("durable telemetry read failed") from exc

    def reset(self) -> None:
        # Never expose a production data-wipe primitive. Tests use memory storage.
        return None


class LiveTelemetryStore:
    """Replay-protected HMAC ingest over a replaceable persistence backend."""

    def __init__(self, persistence: TelemetryPersistence | None = None) -> None:
        self._persistence = persistence or MemoryTelemetryPersistence()

    def reset(self) -> None:
        self._persistence.reset()

    def accept(
        self,
        *,
        body: bytes,
        headers: Mapping[str, str],
        secret: str,
        now: float | None = None,
        parsed_json: Any,
    ) -> dict[str, Any]:
        now = now if now is not None else time.time()
        if len(body) > MAX_BODY_BYTES:
            raise OverflowError("telemetry body exceeds the limit")
        if len(secret) < 32:
            raise RuntimeError("telemetry ingest is not configured")

        timestamp = headers.get("x-sapphire-timestamp", "")
        nonce = headers.get("x-sapphire-nonce", "")
        signature = headers.get("x-sapphire-signature", "").lower()
        try:
            timestamp_i = int(timestamp)
        except ValueError as exc:
            raise PermissionError("invalid telemetry timestamp") from exc
        if abs(now - timestamp_i) > MAX_REQUEST_SKEW_SECONDS:
            raise PermissionError("telemetry timestamp outside allowed skew")
        if not _NONCE_RE.fullmatch(nonce) or not _HEX_RE.fullmatch(signature):
            raise PermissionError("invalid telemetry signature headers")
        message = timestamp.encode() + b"." + nonce.encode() + b"." + body
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("invalid telemetry signature")

        snapshot = validate_snapshot(parsed_json)
        self._persistence.accept(snapshot, nonce=nonce, received_at=now)
        return snapshot

    def get(
        self,
        *,
        public: bool = False,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Return the current snapshot. There is one view; `public` is vestigial.

        The redaction tier is gone (Ari, 2026-07-25): anonymous readers get the
        same numbers, at the same moment, that the operator does. `public` is
        kept only so callers need not change, and there is deliberately no
        `delay_seconds` left to set — the public delay was the last limb of the
        redactor, and a parameter that can still hold data back is a redaction
        tier waiting to be switched on by an environment variable. Capital is
        banded in moss_telemetry: a different store, a deliberate exception.
        """
        now = now if now is not None else time.time()
        selected = self._persistence.select(received_before=now)
        if selected is None:
            return _empty_snapshot(
                status="warming" if self._persistence.has_history() else "offline",
            )

        received_at, snapshot = selected
        try:
            candidate = _normalize_stored(copy.deepcopy(snapshot))
            _require_bounded_structure(candidate)
            projected = validate_snapshot(candidate)
            observed = datetime.fromisoformat(projected["observed_at"]).timestamp()
            if (
                isinstance(received_at, bool)
                or not isinstance(received_at, (int, float))
                or not math.isfinite(float(received_at))
            ):
                raise TelemetryValidationError("invalid durable receive time")
        except Exception:
            return _empty_snapshot(status="offline")
        if observed > now:
            return _empty_snapshot(status="offline")
        freshness_s = round(max(0.0, now - observed), 1)
        status = "live" if freshness_s <= stale_after_seconds else "stale"
        _age_runtime_projection(
            projected,
            now=now,
            snapshot_observed_at=observed,
            stale_after_seconds=stale_after_seconds,
        )
        projected.update(
            {
                "status": status,
                "freshness_s": freshness_s,
                "served_at": datetime.fromtimestamp(now, UTC).isoformat(),
                "received_at": datetime.fromtimestamp(received_at, UTC).isoformat(),
            }
        )
        return projected


def _build_persistence() -> TelemetryPersistence:
    backend = os.getenv("TELEMETRY_STORE", "memory").strip().lower()
    if backend == "firestore":
        return FirestoreTelemetryPersistence(
            collection=os.getenv("TELEMETRY_FIRESTORE_COLLECTION", "sapphire_live_v1"),
            database=os.getenv("TELEMETRY_FIRESTORE_DATABASE") or None,
        )
    if backend != "memory":
        raise RuntimeError("unsupported telemetry persistence backend")
    return MemoryTelemetryPersistence()


store = LiveTelemetryStore(_build_persistence())

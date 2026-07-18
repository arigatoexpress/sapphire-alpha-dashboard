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
DEFAULT_STALE_AFTER_SECONDS = 180

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_IPV4_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_WALLET_RE = re.compile(r"0x[a-fA-F0-9]{40}")

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
_PROVIDERS = {"local GPU", "local CPU", "cloud reasoning", "hybrid", "unassigned"}
_MARKET_STATES = {"current", "delayed", "stale", "offline"}
_GATES = {"telegram", "manual", "off"}
_EXECUTION = {"off", "paper", "gated"}
_EVENT_STATES = {"observed", "verified", "pending", "degraded", "failed", "recovered"}


class TelemetryValidationError(ValueError):
    """Raised when a producer violates the semantic telemetry contract."""


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


def validate_snapshot(raw: Any) -> dict[str, Any]:
    """Return a normalized copy of the only telemetry shape we will store."""
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

    summary_raw = _keys(
        obj["summary"],
        allowed={"state", "active_agents", "events_per_min", "verified_today", "attention"},
        required={"state", "active_agents", "events_per_min", "verified_today", "attention"},
        where="summary",
    )
    summary = {
        "state": _enum(summary_raw["state"], _SUMMARY_STATES, where="summary.state"),
        "active_agents": _integer(summary_raw["active_agents"], where="summary.active_agents", high=100),
        "events_per_min": _number(summary_raw["events_per_min"], where="summary.events_per_min"),
        "verified_today": _integer(summary_raw["verified_today"], where="summary.verified_today"),
        "attention": _integer(summary_raw["attention"], where="summary.attention", high=100),
    }

    if not isinstance(obj["nodes"], list) or len(obj["nodes"]) > 24:
        raise TelemetryValidationError("nodes must be a bounded list")
    nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for index, raw_node in enumerate(obj["nodes"]):
        node = _keys(
            raw_node,
            allowed={"id", "zone", "label", "status", "load_band", "activity_rate", "freshness_s"},
            required={"id", "zone", "label", "status", "load_band", "activity_rate", "freshness_s"},
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
                "load_band": _enum(node["load_band"], _LOAD, where=f"nodes[{index}].load_band"),
                "activity_rate": _number(node["activity_rate"], where=f"nodes[{index}].activity_rate"),
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
                "event_rate": _number(link["event_rate"], where=f"links[{index}].event_rate"),
                "signal_class": _enum(
                    link["signal_class"], _SIGNAL_CLASSES, where=f"links[{index}].signal_class"
                ),
            }
        )

    if not isinstance(obj["agents"], list) or len(obj["agents"]) > 32:
        raise TelemetryValidationError("agents must be a bounded list")
    agents: list[dict[str, Any]] = []
    for index, raw_agent in enumerate(obj["agents"]):
        agent = _keys(
            raw_agent,
            allowed={"id", "role", "state", "activity", "verification", "provider_class", "updated_at"},
            required={"id", "role", "state", "activity", "verification", "provider_class", "updated_at"},
            where=f"agents[{index}]",
        )
        agents.append(
            {
                "id": _identifier(agent["id"], where=f"agents[{index}].id"),
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
        "feed_age_s": _number(market["feed_age_s"], where="markets.feed_age_s", high=86_400),
        "events_per_min": _number(market["events_per_min"], where="markets.events_per_min"),
        "paper_strategies": _integer(market["paper_strategies"], where="markets.paper_strategies", high=100),
        "decision_gate": _enum(market["decision_gate"], _GATES, where="markets.decision_gate"),
        "execution": _enum(market["execution"], _EXECUTION, where="markets.execution"),
    }

    if not isinstance(obj["events"], list) or len(obj["events"]) > 100:
        raise TelemetryValidationError("events must be a bounded list")
    events: list[dict[str, Any]] = []
    for index, raw_event in enumerate(obj["events"]):
        event = _keys(
            raw_event,
            allowed={"id", "observed_at", "event_class", "source", "target", "label", "status"},
            required={"id", "observed_at", "event_class", "source", "target", "label", "status"},
            where=f"events[{index}]",
        )
        events.append(
            {
                "id": _identifier(event["id"], where=f"events[{index}].id"),
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

    return {
        "version": 1,
        "observed_at": observed_at,
        "sequence": sequence,
        "summary": summary,
        "nodes": nodes,
        "links": links,
        "agents": agents,
        "markets": markets,
        "events": events,
    }


def _latency_band(value: float | None) -> str:
    if value is None:
        return "not observed"
    if value < 20:
        return "under 20 ms"
    if value < 80:
        return "20–79 ms"
    if value < 200:
        return "80–199 ms"
    return "200 ms or more"


def _activity_band(value: float) -> str:
    if value <= 0:
        return "quiet"
    if value < 10:
        return "light"
    if value < 60:
        return "active"
    return "busy"


def public_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Bucket timing/rate detail and expose only public narrative fields."""
    out = {
        "version": snapshot["version"],
        "observed_at": snapshot["observed_at"],
        "sequence": snapshot["sequence"],
        "summary": {
            "state": snapshot["summary"]["state"],
            "active_agents": snapshot["summary"]["active_agents"],
            "activity_band": _activity_band(snapshot["summary"]["events_per_min"]),
            "verified_today": snapshot["summary"]["verified_today"],
            "attention": snapshot["summary"]["attention"],
        },
        "nodes": [
            {
                "id": node["id"],
                "zone": node["zone"],
                "label": node["label"],
                "status": node["status"],
                "load_band": node["load_band"],
                "activity_band": _activity_band(node["activity_rate"]),
                "freshness_band": "current" if node["freshness_s"] <= 60 else "delayed",
            }
            for node in snapshot["nodes"]
        ],
        "links": [
            {
                "source": link["source"],
                "target": link["target"],
                "status": link["status"],
                "latency_band": _latency_band(link["latency_ms"]),
                "activity_band": _activity_band(link["event_rate"]),
                "signal_class": link["signal_class"],
            }
            for link in snapshot["links"]
        ],
        "agents": [
            {
                "role": agent["role"],
                "state": agent["state"],
                "activity": agent["activity"],
                "verification": agent["verification"],
                "provider_class": agent["provider_class"],
            }
            for agent in snapshot["agents"]
        ],
        "markets": {
            "network": snapshot["markets"]["network"],
            "status": snapshot["markets"]["status"],
            "feed_freshness": "current" if snapshot["markets"]["feed_age_s"] <= 60 else "delayed",
            "activity_band": _activity_band(snapshot["markets"]["events_per_min"]),
            "paper_strategies": snapshot["markets"]["paper_strategies"],
            "decision_gate": snapshot["markets"]["decision_gate"],
            "execution": snapshot["markets"]["execution"],
        },
        "events": copy.deepcopy(snapshot["events"]),
        "public_view": True,
        "public_policy": "Activity is aggregated and delayed for safety.",
    }
    return out


def _empty_snapshot(*, public: bool, status: str = "offline") -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "version": 1,
        "observed_at": None,
        "sequence": None,
        "summary": {
            "state": "not observed",
            "active_agents": 0,
            "activity_band" if public else "events_per_min": "quiet" if public else 0,
            "verified_today": 0,
            "attention": 0,
        },
        "nodes": [],
        "links": [],
        "agents": [],
        "markets": {
            "network": "Robinhood Chain",
            "status": "offline",
            "feed_freshness" if public else "feed_age_s": "unknown" if public else None,
            "activity_band" if public else "events_per_min": "quiet" if public else 0,
            "paper_strategies": 0,
            "decision_gate": "off",
            "execution": "off",
        },
        "events": [],
        "status": status,
        "freshness_s": None,
        "served_at": now,
        **(
            {
                "public_view": True,
                "public_policy": "Activity is aggregated and delayed for safety.",
            }
            if public
            else {}
        ),
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
        public: bool,
        delay_seconds: float = 0,
        stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
        now: float | None = None,
    ) -> dict[str, Any]:
        now = now if now is not None else time.time()
        target = now - max(0, delay_seconds if public else 0)
        selected = self._persistence.select(received_before=target)
        if selected is None:
            return _empty_snapshot(
                public=public,
                status="warming" if self._persistence.has_history() else "offline",
            )

        received_at, snapshot = selected
        observed = datetime.fromisoformat(snapshot["observed_at"]).timestamp()
        freshness_s = round(max(0.0, now - observed), 1)
        status = "live" if freshness_s <= stale_after_seconds else "stale"
        projected = public_projection(snapshot) if public else copy.deepcopy(snapshot)
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

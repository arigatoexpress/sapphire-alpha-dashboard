"""Signed, durable projection of the sanitized fleet coordination snapshot."""

from __future__ import annotations

import copy
import hashlib
import hmac
import math
import os
import re
import time
from datetime import UTC, datetime
from typing import Any, Mapping

try:
    from .live_telemetry import (
        FirestoreTelemetryPersistence,
        MemoryTelemetryPersistence,
        TelemetryPersistence,
    )
except ImportError:
    from live_telemetry import (
        FirestoreTelemetryPersistence,
        MemoryTelemetryPersistence,
        TelemetryPersistence,
    )


MAX_BODY_BYTES = 64 * 1024
MAX_REQUEST_SKEW_SECONDS = 300
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
_HEX_RE = re.compile(r"^[a-f0-9]{64}$")


class FleetTelemetryValidationError(ValueError):
    pass


def _text(value: Any, *, field: str, limit: int = 120) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise FleetTelemetryValidationError(f"{field} must be bounded text")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 48:
        raise FleetTelemetryValidationError("generated_at must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FleetTelemetryValidationError(
            "generated_at must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.timestamp() > time.time() + 60:
        raise FleetTelemetryValidationError(
            "generated_at must be a current zoned timestamp"
        )
    return parsed.astimezone(UTC).isoformat()


def validate_fleet_snapshot(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {
        "version",
        "generated_at",
        "sequence",
        "leases",
        "gates",
        "counts",
    }:
        raise FleetTelemetryValidationError(
            "fleet telemetry has unsupported or missing fields"
        )
    if raw["version"] != 1:
        raise FleetTelemetryValidationError("unsupported fleet telemetry version")
    sequence = raw["sequence"]
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 0
    ):
        raise FleetTelemetryValidationError(
            "fleet telemetry sequence must be a non-negative integer"
        )
    raw_leases = raw["leases"]
    raw_gates = raw["gates"]
    if (
        not isinstance(raw_leases, list)
        or not isinstance(raw_gates, list)
        or len(raw_leases) > 100
        or len(raw_gates) > 100
    ):
        raise FleetTelemetryValidationError("fleet telemetry lists are invalid")

    leases: list[dict[str, Any]] = []
    for index, lease in enumerate(raw_leases):
        if not isinstance(lease, dict) or set(lease) != {
            "agent",
            "repo",
            "purpose",
            "expires_at",
        }:
            raise FleetTelemetryValidationError("fleet lease is invalid")
        leases.append(
            {
                field: _text(
                    lease[field],
                    field=f"leases[{index}].{field}",
                )
                for field in ("agent", "repo", "purpose", "expires_at")
            }
        )

    gates: list[dict[str, Any]] = []
    for index, gate in enumerate(raw_gates):
        if not isinstance(gate, dict) or set(gate) != {
            "id",
            "title",
            "age_hours",
            "status",
        }:
            raise FleetTelemetryValidationError("fleet gate is invalid")
        gate_id = gate["id"]
        age_hours = gate["age_hours"]
        if (
            not isinstance(gate_id, int)
            or isinstance(gate_id, bool)
            or not isinstance(age_hours, (int, float))
            or isinstance(age_hours, bool)
            or not math.isfinite(float(age_hours))
            or float(age_hours) < 0
        ):
            raise FleetTelemetryValidationError("fleet gate values are invalid")
        gates.append(
            {
                "id": gate_id,
                "title": _text(
                    gate["title"], field=f"gates[{index}].title"
                ),
                "age_hours": round(float(age_hours), 3),
                "status": _text(
                    gate["status"], field=f"gates[{index}].status", limit=32
                ),
            }
        )

    counts = raw["counts"]
    if (
        not isinstance(counts, dict)
        or set(counts) != {"leases", "gates_open"}
        or counts["leases"] != len(leases)
        or counts["gates_open"] != len(gates)
    ):
        raise FleetTelemetryValidationError("fleet telemetry counts mismatch")

    return {
        "version": 1,
        "generated_at": _timestamp(raw["generated_at"]),
        "sequence": sequence,
        "leases": leases,
        "gates": gates,
        "counts": {"leases": len(leases), "gates_open": len(gates)},
    }


class FleetTelemetryStore:
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
        parsed_json: Any,
        now: float | None = None,
    ) -> dict[str, Any]:
        now = time.time() if now is None else now
        if len(body) > MAX_BODY_BYTES:
            raise OverflowError("fleet telemetry body exceeds the limit")
        if len(secret) < 32:
            raise RuntimeError("fleet telemetry ingest is not configured")
        timestamp = headers.get("x-sapphire-timestamp", "")
        nonce = headers.get("x-sapphire-nonce", "")
        signature = headers.get("x-sapphire-signature", "").lower()
        try:
            timestamp_i = int(timestamp)
        except ValueError as exc:
            raise PermissionError("invalid fleet telemetry timestamp") from exc
        if abs(now - timestamp_i) > MAX_REQUEST_SKEW_SECONDS:
            raise PermissionError("fleet telemetry timestamp outside allowed skew")
        if not _NONCE_RE.fullmatch(nonce) or not _HEX_RE.fullmatch(signature):
            raise PermissionError("invalid fleet telemetry signature headers")
        message = timestamp.encode() + b"." + nonce.encode() + b"." + body
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("invalid fleet telemetry signature")
        snapshot = validate_fleet_snapshot(parsed_json)
        self._persistence.accept(snapshot, nonce=nonce, received_at=now)
        return snapshot

    def get(self) -> dict[str, Any] | None:
        selected = self._persistence.select(received_before=time.time())
        if selected is None:
            return None
        try:
            return validate_fleet_snapshot(copy.deepcopy(selected[1]))
        except FleetTelemetryValidationError:
            return None


def _build_persistence() -> TelemetryPersistence:
    backend = os.getenv("TELEMETRY_STORE", "memory").strip().lower()
    if backend == "firestore":
        return FirestoreTelemetryPersistence(
            collection=os.getenv(
                "FLEET_TELEMETRY_FIRESTORE_COLLECTION",
                "sapphire_fleet_v1",
            ),
            database=os.getenv("TELEMETRY_FIRESTORE_DATABASE") or None,
        )
    if backend != "memory":
        raise RuntimeError("unsupported telemetry persistence backend")
    return MemoryTelemetryPersistence()


store = FleetTelemetryStore(_build_persistence())

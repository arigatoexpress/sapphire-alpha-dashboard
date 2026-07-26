"""Dedicated, replay-protected telemetry for the private local MOSS observer.

The general Signal Routes contract intentionally rejects wallet and balance fields.
This separate boundary retains exact decimal strings for authenticated operators
and emits a non-fingerprinting public projection.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import os
import re
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
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


MAX_BODY_BYTES = 8 * 1024
MAX_REQUEST_SKEW_SECONDS = 300
STALE_AFTER_SECONDS = 180
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
_MASKED_ID_RE = re.compile(r"^0x[a-fA-F0-9]{4}…[a-fA-F0-9]{4}$")
_DECIMAL_RE = re.compile(r"^\d+(?:\.\d+)?$")
_BLOCK_RE = re.compile(r"^\d+$")
_FULL_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")


class MossTelemetryValidationError(ValueError):
    pass


def _exact_keys(value: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MossTelemetryValidationError("MOSS telemetry must be an object")
    if set(value) != allowed:
        raise MossTelemetryValidationError("MOSS telemetry has unsupported or missing fields")
    return value


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 48:
        raise MossTelemetryValidationError("observed_at must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MossTelemetryValidationError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.timestamp() > time.time() + 60:
        raise MossTelemetryValidationError("observed_at must be a current zoned timestamp")
    return parsed.astimezone(UTC).isoformat()


def _units(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) > 80 or not _DECIMAL_RE.fullmatch(value):
        raise MossTelemetryValidationError(f"{field} must be non-negative decimal units")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise MossTelemetryValidationError(f"{field} must be decimal units") from exc
    if not parsed.is_finite() or parsed < 0:
        raise MossTelemetryValidationError(f"{field} must be non-negative decimal units")
    return value


def validate_moss_snapshot(raw: Any) -> dict[str, Any]:
    fields = {
        "version",
        "observed_at",
        "sequence",
        "chain",
        "identity_masked",
        "usdm",
        "eth",
        "block",
    }
    obj = _exact_keys(raw, fields)
    if _FULL_ADDRESS_RE.search(str(raw)):
        raise MossTelemetryValidationError("full addresses are forbidden")
    if obj["version"] != 1:
        raise MossTelemetryValidationError("unsupported MOSS telemetry version")
    if not isinstance(obj["sequence"], int) or isinstance(obj["sequence"], bool) or obj["sequence"] < 0:
        raise MossTelemetryValidationError("sequence must be a non-negative integer")
    if obj["chain"] != "MegaETH Mainnet":
        raise MossTelemetryValidationError("MOSS telemetry chain mismatch")
    if not isinstance(obj["identity_masked"], str) or not _MASKED_ID_RE.fullmatch(obj["identity_masked"]):
        raise MossTelemetryValidationError("identity must be masked")
    if not isinstance(obj["block"], str) or len(obj["block"]) > 32 or not _BLOCK_RE.fullmatch(obj["block"]):
        raise MossTelemetryValidationError("block must be a decimal string")
    return {
        "version": 1,
        "observed_at": _timestamp(obj["observed_at"]),
        "sequence": obj["sequence"],
        "chain": "MegaETH Mainnet",
        "identity_masked": obj["identity_masked"],
        "usdm": _units(obj["usdm"], "usdm"),
        "eth": _units(obj["eth"], "eth"),
        "block": obj["block"],
    }


def _usdm_band(value: str) -> str:
    amount = Decimal(value)
    if amount == 0:
        return "$0"
    if amount < 100:
        return "$1–$99"
    if amount < 250:
        return "$100–$249"
    if amount < 1_000:
        return "$250–$999"
    if amount < 10_000:
        return "$1k–$9.9k"
    return "$10k+"


def _freshness_band(age: float) -> str:
    if age <= 60:
        return "current"
    if age <= 300:
        return "delayed"
    return "stale"


def public_projection(snapshot: dict[str, Any], *, now: float) -> dict[str, Any]:
    observed = datetime.fromisoformat(snapshot["observed_at"]).timestamp()
    age = max(0.0, now - observed)
    return {
        "version": 1,
        "network": "MegaETH",
        "asset": "USDm",
        "usdm_band": _usdm_band(snapshot["usdm"]),
        "eth_state": "present" if Decimal(snapshot["eth"]) > 0 else "empty",
        "observation_freshness": _freshness_band(age),
        "custody": "hosted passkey",
        "authority": "read-only",
        "public_view": True,
        "public_policy": "Capital is banded and identity is withheld.",
    }


def _empty(*, public: bool, now: float) -> dict[str, Any]:
    base = {
        "version": 1,
        "network": "MegaETH",
        "status": "offline",
        "freshness_s": None,
        "served_at": datetime.fromtimestamp(now, UTC).isoformat(),
    }
    if public:
        base.update(
            {
                "asset": "USDm",
                "usdm_band": "not observed",
                "eth_state": "not observed",
                "observation_freshness": "not observed",
                "custody": "hosted passkey",
                "authority": "read-only",
                "public_view": True,
            }
        )
    return base


class MossTelemetryStore:
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
            raise OverflowError("MOSS telemetry body exceeds the limit")
        if len(secret) < 32:
            raise RuntimeError("MOSS telemetry ingest is not configured")
        timestamp = headers.get("x-sapphire-timestamp", "")
        nonce = headers.get("x-sapphire-nonce", "")
        signature = headers.get("x-sapphire-signature", "").lower()
        try:
            timestamp_i = int(timestamp)
        except ValueError as exc:
            raise PermissionError("invalid MOSS telemetry timestamp") from exc
        if abs(now - timestamp_i) > MAX_REQUEST_SKEW_SECONDS:
            raise PermissionError("MOSS telemetry timestamp outside allowed skew")
        if not _NONCE_RE.fullmatch(nonce) or not _HEX_RE.fullmatch(signature):
            raise PermissionError("invalid MOSS telemetry signature headers")
        message = timestamp.encode() + b"." + nonce.encode() + b"." + body
        expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError("invalid MOSS telemetry signature")
        snapshot = validate_moss_snapshot(parsed_json)
        self._persistence.accept(snapshot, nonce=nonce, received_at=now)
        return snapshot

    def get(self, *, public: bool, delay_seconds: float = 0, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        target = now - max(0.0, delay_seconds if public else 0.0)
        selected = self._persistence.select(received_before=target)
        if selected is None:
            return _empty(public=public, now=now)
        received_at, snapshot = selected
        observed = datetime.fromisoformat(snapshot["observed_at"]).timestamp()
        freshness_s = round(max(0.0, now - observed), 1)
        output = public_projection(snapshot, now=now) if public else copy.deepcopy(snapshot)
        output.update(
            {
                "status": "live" if freshness_s <= STALE_AFTER_SECONDS else "stale",
                "freshness_s": freshness_s,
                "served_at": datetime.fromtimestamp(now, UTC).isoformat(),
                "received_at": datetime.fromtimestamp(received_at, UTC).isoformat(),
            }
        )
        if not public:
            output["public_view"] = False
        return output


def _build_persistence() -> TelemetryPersistence:
    backend = os.getenv("TELEMETRY_STORE", "memory").strip().lower()
    if backend == "firestore":
        return FirestoreTelemetryPersistence(
            collection=os.getenv("MOSS_TELEMETRY_FIRESTORE_COLLECTION", "sapphire_moss_v1"),
            database=os.getenv("TELEMETRY_FIRESTORE_DATABASE") or None,
        )
    if backend != "memory":
        raise RuntimeError("unsupported telemetry persistence backend")
    return MemoryTelemetryPersistence()


store = MossTelemetryStore(_build_persistence())

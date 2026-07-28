"""Owner-only, local-only attended approval rail.

This module records one exact attended decision through the installed
``fleet_lease.approvals`` lifecycle API. It has no executor, adapter, outbox,
network, process, credential-creation, or external-action path. Production
activation is absent until a separately attended, MAC-authenticated local
attestation is installed.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import types
from types import MappingProxyType
from typing import Any, Protocol

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict


DISPLAY_SCHEMA = "owner-approval-display/v1"
ACTIVATION_SCHEMA = "owner-approval-activation/v1"
CHALLENGE_SCHEMA = "owner-approval-challenge/v1"
RECEIPT_SCHEMA = "owner-approval-attended-receipt/v1"
OWNER_IDENTITY = "ari"
OWNER_CLASS = "HUMAN_ATTENDED"
SESSION_COOKIE = "sapphire_owner_session"
MAX_CHALLENGE_SECONDS = 60
CANONICAL_REGISTRY_PATH = (Path.home() / "ops-state" / "fleet-lease.db").resolve()
ACTIVATION_PATH = (
    Path.home() / "ops-state" / "owner-approval-rail" / "activation.json"
).resolve()
ACTIVATION_KEY_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Sapphire"
    / "owner-approval-rail.key"
).resolve()
SESSION_REGISTRY_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Sapphire"
    / "owner-approval-sessions.sqlite3"
).resolve()
FLEET_LEASE_SOURCE_ROOT = (
    Path.home() / "Code" / "fleet-lease" / "src" / "fleet_lease"
).resolve()

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
_CLOUD_MARKERS = frozenset(
    {
        "K_SERVICE",
        "K_REVISION",
        "K_CONFIGURATION",
        "CLOUD_RUN_JOB",
        "GAE_SERVICE",
        "FUNCTION_TARGET",
        "KUBERNETES_SERVICE_HOST",
        "ECS_CONTAINER_METADATA_URI",
    }
)
_TERMINAL_STATUSES = frozenset(
    {"APPROVED", "EXECUTING", "PARTIAL", "DONE", "EXPIRED", "REVOKED"}
)
DISPLAY_ACTION_FIELDS = (
    "action_id",
    "action_kind",
    "atomic_group",
    "environment",
    "account",
    "destination",
    "parameters",
    "units",
    "max_cost",
    "max_slippage_bps",
    "target_revision_sha256",
    "idempotency_key",
    "preconditions",
    "expected_effects",
    "verification",
    "rollback",
    "kill_switch",
    "residual_risks",
    "financial",
)
DISPLAY_FINANCIAL_FIELDS = (
    "account",
    "symbol",
    "asset",
    "side",
    "quantity",
    "max_notional",
    "order_type",
    "limit_price",
    "stop_price",
    "time_in_force",
    "estimated_fees",
    "max_slippage_bps",
    "market_hours_policy",
)
DISPLAY_REVIEW_FIELDS = (
    "reviewer",
    "reviewer_class",
    "verdict",
    "reviewed_at",
    "candidate_sha256",
    "artifact_sha256",
)


DEPENDENCY_PINS: Mapping[str, str | int] = MappingProxyType(
    {
        "schema_version": "owner-approval-dependencies/v1",
        "preflight_sha256": "0031e4c1abae3aca97463757ba32016bd0ce1e3b432e25394b02e9e64da68b8f",
        "task053_candidate_commit": "fc17c6105f4522af473818081199b272bbb90718",
        "task053_candidate_tree": "5ac267d26ce46eca8d47e54b85c7526200808c42",
        "task053_result_sha256": "873695a0b2f8bfbb519b946976be43d77aa2e2cb7e172c56769c145b6d76f719",
        "task053_review_sha256": "27f57f2ecb14c06280c383741850deb04aa557e02d8f9da93e15829e717092a4",
        "task061_merged_commit": "74f334942f0161861439ffc78b12898a0700600b",
        "task061_merged_tree": "44d44b83c23c18758b81caee143c8adae067e92a",
        "task061_result_sha256": "40daab4625cd93ba71385aba0863077af5bf3bcc7b6a31f08604bf63518ce7a5",
        "task061_review_sha256": "8f56f716cc4d4cb98193c32cb1996375e630228164c15d0eceebfef11764d0b0",
        "fleet_lease_version": "0.7.1",
        "approval_schema_version": "3.1.0",
        "approval_source_size": 185320,
        "approval_source_sha256": "3ad1de8d2e8eb0c930f32487d5ce8e65363ad9c96f83f4bf165f62f7153a7784",
        "fleet_core_source_size": 10381,
        "fleet_core_source_sha256": "5ba04bd3092ac0093d15da8313302ffa9861a2f8249666a889839beb916d001d",
        "fleet_lease_runtime_commit": "66c404925ce64222d3fe1f4688cadb973c8d424f",
        "fleet_lease_runtime_tree": "2348814fe79ae096eb16500b448cde32f45d223c",
        "approval_harness_merged_commit": "66c404925ce64222d3fe1f4688cadb973c8d424f",
        "approval_harness_merged_tree": "2348814fe79ae096eb16500b448cde32f45d223c",
        "task059_merged_commit": "94d4df4d0b3bdbd11b10679c74d316936f8dec08",
        "task059_merged_tree": "0723948e4b730710ad0553bafa01e4f98eb0f94e",
        "task059_result_sha256": "5866a7dea2c0e677ea7109cd8f024028c76d59f8c589f4d6d4f8482766dec745",
        "task059_review_sha256": "27a4bc76e35d9bf3cc2a63ececc40639b5eb87995a9013d9422a63f4de436d51",
        "approval_consumer_source_sha256": "ad1a8b30a9005d99926673a0d867b6766d20038ae7cf939c2e65023a48e43dd3",
        "production_execution_available": 0,
    }
)

_PROTECTED_LABELS = (
    "owner-approval-rail",
    "owner-basic-auth-boundary",
    "owner-approval-local-fence",
    "owner-approval-activation-attestation",
    "owner-approval-activation-key",
    "owner-approval-authority-registry",
    "owner-approval-session-registry",
    "owner-approval-local-launcher",
    "owner-approval-cloud-deployment",
)
_PROTECTED_AUTHORITY_CLASSES = (
    ("SERVICE", "svc"),
    ("DESTINATION", "dest"),
    ("ENVIRONMENT", "env"),
    ("ACCOUNT", "acct"),
)


def canonical_json(value: object) -> str:
    """Return the one bounded canonical representation used for local hashes."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _protected_authority_id(
    label: str,
    authority_class: str,
    prefix: str,
) -> str:
    descriptor = {
        "schema_version": "1.0.0",
        "authority_class": authority_class,
        "resource_id": (
            "resource:"
            + hashlib.sha256(
                f"sapphire-owner-approval:{label}".encode("ascii")
            ).hexdigest()
        ),
        "scope_cardinality": "ONE",
    }
    return f"{prefix}:{canonical_sha256(descriptor)}"


PROTECTED_AUTHORITY_IDS = tuple(
    _protected_authority_id(label, authority_class, prefix)
    for label in _PROTECTED_LABELS
    for authority_class, prefix in _PROTECTED_AUTHORITY_CLASSES
) + (
    DEPENDENCY_PINS["approval_source_sha256"],
    DEPENDENCY_PINS["fleet_core_source_sha256"],
)


PIN_SET_SHA256 = canonical_sha256(dict(DEPENDENCY_PINS))


class RailRefused(RuntimeError):
    """One closed approval-rail refusal without private input reflection."""

    def __init__(self, code: str, status_code: int = 409):
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,63}", code):
            code = "RAIL_REFUSED"
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ActivationState:
    active: bool
    reason_code: str
    pin_set_sha256: str
    registry_identity_sha256: str
    protected_authority_ids: tuple[str, ...]
    expires_at: str | None

    @classmethod
    def inactive(cls, reason_code: str) -> ActivationState:
        return cls(
            active=False,
            reason_code=reason_code,
            pin_set_sha256=PIN_SET_SHA256,
            registry_identity_sha256="",
            protected_authority_ids=(),
            expires_at=None,
        )


@dataclass(frozen=True, slots=True)
class ChallengeIssue:
    session_cookie: str
    csrf_challenge: str
    expires_at: str


class CompilerPort(Protocol):
    """Narrow installed compiler boundary; there is deliberately no executor."""

    def get_bundle(self, bundle_id: str) -> dict[str, Any]: ...

    def verify_bundle_integrity(self, bundle_id: str) -> dict[str, Any]: ...

    def bundle_receipts(self, bundle_id: str) -> list[dict[str, Any]]: ...

    def provision_attended_approval_receipt(
        self,
        content: dict[str, Any],
        *,
        operation_key: str,
    ) -> str: ...

    def consume_legacy_owner_activation(self, **kwargs: str) -> bool: ...

    def approve_bundle(self, bundle_id: str, **kwargs: object) -> dict[str, Any]: ...

    def revoke_bundle(self, bundle_id: str, **kwargs: object) -> dict[str, Any]: ...


def _parse_utc(value: object) -> datetime:
    if type(value) is not str:
        raise RailRefused("BUNDLE_INCOMPLETE")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise RailRefused("BUNDLE_INCOMPLETE") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RailRefused("BUNDLE_INCOMPLETE")
    return parsed.astimezone(UTC)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _opaque(size: int, token_bytes: Callable[[int], bytes]) -> str:
    raw = token_bytes(size)
    if type(raw) is not bytes or len(raw) != size:
        raise RailRefused("RANDOM_SOURCE_INVALID", 503)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _secret_hash(domain: str, value: str) -> str:
    if type(domain) is not str or type(value) is not str:
        raise RailRefused("CHALLENGE_INVALID")
    return hashlib.sha256(f"{domain}\0{value}".encode("utf-8")).hexdigest()


def _owner_private_file(path: Path) -> bool:
    if type(path) is not type(CANONICAL_REGISTRY_PATH):
        return False
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    return (
        resolved == path
        and not path.is_symlink()
        and stat.S_ISREG(metadata.st_mode)
        and metadata.st_nlink == 1
        and stat.S_IMODE(metadata.st_mode) == 0o600
        and (not hasattr(os, "geteuid") or metadata.st_uid == os.geteuid())
    )


def registry_identity_sha256(path: Path) -> str:
    """Bind one canonical owner file without pretending its mutable bytes are static."""
    if not _owner_private_file(path):
        raise RailRefused("REGISTRY_IDENTITY_INVALID", 503)
    metadata = path.stat()
    return canonical_sha256(
        {
            "schema_version": "owner-approval-registry-identity/v1",
            "canonical_path": str(path),
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "owner_uid": metadata.st_uid,
            "mode": stat.S_IMODE(metadata.st_mode),
        }
    )


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > 64 * 1024:
        raise RailRefused("ACTIVATION_FILE_INVALID", 503)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if type(key) is not str or key in result:
                raise RailRefused("ACTIVATION_FILE_INVALID", 503)
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs)
    except (UnicodeError, ValueError, json.JSONDecodeError):
        raise RailRefused("ACTIVATION_FILE_INVALID", 503) from None
    if type(value) is not dict:
        raise RailRefused("ACTIVATION_FILE_INVALID", 503)
    return value


class ActivationVerifier:
    """Verify the separately attended activation; it never creates one."""

    _FIELDS = frozenset(
        {
            "schema_version",
            "scope",
            "pin_set_sha256",
            "registry_identity_sha256",
            "legacy_gate_receipt_sha256",
            "nonce_sha256",
            "issued_at",
            "expires_at",
            "mac_sha256",
        }
    )

    def __init__(
        self,
        *,
        registry_path: Path,
        attestation_path: Path,
        key_path: Path,
        consume_legacy_receipt: Callable[..., bool],
    ) -> None:
        self._registry_path = registry_path
        self._attestation_path = attestation_path
        self._key_path = key_path
        self._consume_legacy_receipt = consume_legacy_receipt

    def verify(self, now: datetime) -> ActivationState:
        if not (
            _owner_private_file(self._registry_path)
            and _owner_private_file(self._attestation_path)
            and _owner_private_file(self._key_path)
        ):
            return ActivationState.inactive("ACTIVATION_FILE_INVALID")
        try:
            document = _strict_json_object(self._attestation_path.read_bytes())
            key = self._key_path.read_bytes()
        except (OSError, RailRefused):
            return ActivationState.inactive("ACTIVATION_FILE_INVALID")
        if len(key) < 32 or frozenset(document) != self._FIELDS:
            return ActivationState.inactive("ACTIVATION_FILE_INVALID")
        if (
            document.get("schema_version") != ACTIVATION_SCHEMA
            or document.get("scope") != "LOCAL_OWNER_APPROVAL_RAIL"
            or document.get("pin_set_sha256") != PIN_SET_SHA256
        ):
            return ActivationState.inactive("ACTIVATION_BINDING_INVALID")
        try:
            registry_identity = registry_identity_sha256(self._registry_path)
            issued = _parse_utc(document["issued_at"])
            expires = _parse_utc(document["expires_at"])
        except RailRefused:
            return ActivationState.inactive("ACTIVATION_BINDING_INVALID")
        if (
            document.get("registry_identity_sha256") != registry_identity
            or not _SHA256_RE.fullmatch(
                str(document.get("legacy_gate_receipt_sha256", ""))
            )
            or document["legacy_gate_receipt_sha256"] == "0" * 64
            or not _SHA256_RE.fullmatch(str(document.get("nonce_sha256", "")))
            or document["nonce_sha256"] == "0" * 64
            or now.tzinfo is None
            or now.astimezone(UTC) < issued
            or now.astimezone(UTC) >= expires
            or expires > issued + timedelta(hours=24)
        ):
            return ActivationState.inactive("ACTIVATION_BINDING_INVALID")
        supplied = document.get("mac_sha256")
        unsigned = {
            key_name: value
            for key_name, value in document.items()
            if key_name != "mac_sha256"
        }
        expected = hmac.new(
            key,
            canonical_json(unsigned).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if type(supplied) is not str or not hmac.compare_digest(supplied, expected):
            return ActivationState.inactive("ACTIVATION_MAC_INVALID")
        activation_sha256 = canonical_sha256(document)
        try:
            consumed = self._consume_legacy_receipt(
                receipt_sha256=document["legacy_gate_receipt_sha256"],
                activation_sha256=activation_sha256,
                owner_identity=OWNER_IDENTITY,
                scope=document["scope"],
                pin_set_sha256=document["pin_set_sha256"],
                registry_identity_sha256=document["registry_identity_sha256"],
                nonce_sha256=document["nonce_sha256"],
            )
        except Exception:
            return ActivationState.inactive("LEGACY_RECEIPT_INVALID")
        if consumed is not True:
            return ActivationState.inactive("LEGACY_RECEIPT_INVALID")
        return ActivationState(
            active=True,
            reason_code="ACTIVE",
            pin_set_sha256=PIN_SET_SHA256,
            registry_identity_sha256=registry_identity,
            protected_authority_ids=PROTECTED_AUTHORITY_IDS,
            expires_at=_utc(expires),
        )


def _artifact_matches(path: Path, expected: str) -> bool:
    return _owner_private_file(path) and hmac.compare_digest(
        hashlib.sha256(path.read_bytes()).hexdigest(), expected
    )


class ChallengeMacAuthority:
    """Domain-separated challenge authority backed by the activation key."""

    _DOMAIN = b"owner-approval-session-challenge/v1\0"

    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path

    def _key(self) -> bytes:
        try:
            descriptor = os.open(
                self._key_path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
        except OSError:
            raise RailRefused("CHALLENGE_AUTHORITY_UNAVAILABLE", 503) from None
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) != 0o600
                or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
                or not 32 <= before.st_size <= 4096
            ):
                raise RailRefused("CHALLENGE_AUTHORITY_UNAVAILABLE", 503)
            key = os.read(descriptor, 4097)
            after = os.fstat(descriptor)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise RailRefused("CHALLENGE_AUTHORITY_UNAVAILABLE", 503)
        finally:
            os.close(descriptor)
        if len(key) != before.st_size:
            raise RailRefused("CHALLENGE_AUTHORITY_UNAVAILABLE", 503)
        return key

    def attest(self, content: dict) -> str:
        if type(content) is not dict:
            raise RailRefused("CHALLENGE_INVALID")
        return hmac.new(
            self._key(),
            self._DOMAIN + canonical_json(content).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, content: dict, supplied_mac: str) -> bool:
        if type(supplied_mac) is not str or not _SHA256_RE.fullmatch(supplied_mac):
            return False
        try:
            expected = self.attest(content)
        except RailRefused:
            return False
        return hmac.compare_digest(supplied_mac, expected)


class FleetLeaseCompilerPort:
    """Execute the same held, verified public lifecycle implementation."""

    def __init__(
        self,
        *,
        challenge_verifier: Callable[[dict, str], bool],
    ) -> None:
        self._database: Any | None = None
        self._challenge_verifier = challenge_verifier

    @staticmethod
    def _held_source(path: Path, expected_size: int, expected_sha256: str) -> bytes:
        try:
            if path.resolve(strict=True) != path or path.is_symlink():
                raise OSError
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
        except OSError:
            raise RailRefused("DEPENDENCY_MISMATCH", 503) from None
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
                or before.st_size != expected_size
            ):
                raise RailRefused("DEPENDENCY_MISMATCH", 503)
            chunks: list[bytes] = []
            remaining = expected_size + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            after = os.fstat(descriptor)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise RailRefused("DEPENDENCY_MISMATCH", 503)
        finally:
            os.close(descriptor)
        if len(content) != expected_size or not hmac.compare_digest(
            hashlib.sha256(content).hexdigest(),
            expected_sha256,
        ):
            raise RailRefused("DEPENDENCY_MISMATCH", 503)
        return content

    @classmethod
    def _load_held_database(
        cls,
        *,
        registry_path: Path,
        core_path: Path,
        approvals_path: Path,
        core_size: int,
        core_sha256: str,
        approvals_size: int,
        approvals_sha256: str,
        schema_version: str,
        challenge_verifier: Callable[[dict, str], bool],
    ) -> Any:
        core_source = cls._held_source(core_path, core_size, core_sha256)
        approvals_source = cls._held_source(
            approvals_path,
            approvals_size,
            approvals_sha256,
        )
        package_name = (
            "_sapphire_held_fleet_"
            + hashlib.sha256(core_source + approvals_source).hexdigest()[:20]
            + f"_{id(core_source):x}"
        )
        if package_name in sys.modules:
            raise RailRefused("DEPENDENCY_MISMATCH", 503)
        package = types.ModuleType(package_name)
        package.__path__ = []
        package.__package__ = package_name
        core = types.ModuleType(package_name + ".core")
        core.__package__ = package_name
        core.__file__ = str(core_path)
        approvals = types.ModuleType(package_name + ".approvals")
        approvals.__package__ = package_name
        approvals.__file__ = str(approvals_path)
        sys.modules[package_name] = package
        sys.modules[core.__name__] = core
        sys.modules[approvals.__name__] = approvals
        try:
            exec(compile(core_source, str(core_path), "exec"), core.__dict__)
            exec(
                compile(approvals_source, str(approvals_path), "exec"),
                approvals.__dict__,
            )
            if approvals.BUNDLE_SCHEMA_VERSION != schema_version:
                raise RailRefused("DEPENDENCY_MISMATCH", 503)
            return approvals.ApprovalBundleDB(
                registry_path,
                _attended_challenge_verifier=challenge_verifier,
            )
        except RailRefused:
            raise
        except Exception:
            raise RailRefused("DEPENDENCY_MISMATCH", 503) from None

    @staticmethod
    def _verify_evidence() -> None:
        if not _owner_private_file(CANONICAL_REGISTRY_PATH):
            raise RailRefused("REGISTRY_IDENTITY_INVALID", 503)
        done = Path.home() / "ops-state" / "orchestrator-package-v1.0.0" / "DONE"
        reviews = Path.home() / "ops-state" / "reviews"
        artifacts = (
            (
                done / "SAPPHIRE-ORCHESTRATOR-20260728-053-result-r11.md",
                "task053_result_sha256",
            ),
            (
                reviews
                / "SAPPHIRE-ORCHESTRATOR-20260728-053-independent-review-r11.md",
                "task053_review_sha256",
            ),
            (
                done / "SAPPHIRE-ORCHESTRATOR-20260728-061-result-r1.md",
                "task061_result_sha256",
            ),
            (
                reviews / "SAPPHIRE-ORCHESTRATOR-20260728-061-independent-review-r1.md",
                "task061_review_sha256",
            ),
            (
                done / "SAPPHIRE-ORCHESTRATOR-20260728-059-result-r3.md",
                "task059_result_sha256",
            ),
            (
                reviews / "SAPPHIRE-ORCHESTRATOR-20260728-059-independent-review-r3.md",
                "task059_review_sha256",
            ),
        )
        if any(
            not _artifact_matches(path, str(DEPENDENCY_PINS[key]))
            for path, key in artifacts
        ):
            raise RailRefused("DEPENDENCY_MISMATCH", 503)

    def _db(self) -> Any:
        if self._database is None:
            self._verify_evidence()
            core_path = FLEET_LEASE_SOURCE_ROOT / "core.py"
            approvals_path = FLEET_LEASE_SOURCE_ROOT / "approvals.py"
            self._database = self._load_held_database(
                registry_path=CANONICAL_REGISTRY_PATH,
                core_path=core_path,
                approvals_path=approvals_path,
                core_size=int(DEPENDENCY_PINS["fleet_core_source_size"]),
                core_sha256=str(DEPENDENCY_PINS["fleet_core_source_sha256"]),
                approvals_size=int(DEPENDENCY_PINS["approval_source_size"]),
                approvals_sha256=str(DEPENDENCY_PINS["approval_source_sha256"]),
                schema_version=str(DEPENDENCY_PINS["approval_schema_version"]),
                challenge_verifier=self._challenge_verifier,
            )
        return self._database

    def get_bundle(self, bundle_id: str) -> dict[str, Any]:
        return self._db().get_bundle(bundle_id)

    def verify_bundle_integrity(self, bundle_id: str) -> dict[str, Any]:
        return self._db().verify_bundle_integrity(bundle_id)

    def bundle_receipts(self, bundle_id: str) -> list[dict[str, Any]]:
        return self._db().bundle_receipts(bundle_id)

    def provision_attended_approval_receipt(
        self,
        content: dict[str, Any],
        *,
        operation_key: str,
    ) -> str:
        return self._db().provision_attended_approval_receipt(
            content,
            operation_key=operation_key,
        )

    def consume_legacy_owner_activation(self, **kwargs: str) -> bool:
        return self._db().consume_legacy_owner_activation(**kwargs)

    def approve_bundle(self, bundle_id: str, **kwargs: object) -> dict[str, Any]:
        return self._db().approve_bundle(bundle_id, **kwargs)

    def revoke_bundle(self, bundle_id: str, **kwargs: object) -> dict[str, Any]:
        return self._db().revoke_bundle(bundle_id, **kwargs)


_RAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS owner_approval_rail_challenges (
    challenge_sha256 TEXT PRIMARY KEY,
    session_sha256 TEXT NOT NULL UNIQUE,
    csrf_sha256 TEXT NOT NULL UNIQUE,
    owner_identity TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    bundle_sha256 TEXT NOT NULL,
    expected_rev INTEGER NOT NULL,
    statement_sha256 TEXT NOT NULL,
    pin_set_sha256 TEXT NOT NULL,
    registry_identity_sha256 TEXT NOT NULL,
    challenge_attestation_sha256 TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL,
    decision TEXT,
    operation_key TEXT,
    result_json TEXT
);
CREATE INDEX IF NOT EXISTS owner_approval_rail_bundle_state
ON owner_approval_rail_challenges(bundle_id, owner_identity, state);
"""


class OwnerApprovalRail:
    """One exact inspection/challenge/decision state machine."""

    def __init__(
        self,
        *,
        compiler: CompilerPort,
        activation: Callable[[datetime], ActivationState],
        clock: Callable[[], datetime],
        token_bytes: Callable[[int], bytes],
        session_registry_path: Path,
        challenge_attestor: Callable[[dict], str],
    ) -> None:
        self._compiler = compiler
        self._activation = activation
        self._clock = clock
        self._token_bytes = token_bytes
        self._session_registry_path = Path(os.path.abspath(session_registry_path))
        self._challenge_attestor = challenge_attestor

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise RailRefused("CLOCK_INVALID", 503)
        return value.astimezone(UTC)

    def _activation_now(self, now: datetime) -> ActivationState:
        state = self._activation(now)
        if type(state) is not ActivationState:
            raise RailRefused("ACTIVATION_INVALID", 503)
        return state

    def _compile_evidence(
        self,
        bundle_id: str,
        bundle_sha256: str,
    ) -> tuple[str, str]:
        try:
            receipts = self._compiler.bundle_receipts(bundle_id)
        except Exception:
            raise RailRefused("BUNDLE_INVALID", 409) from None
        compiled = [
            item
            for item in receipts
            if type(item) is dict and item.get("event_type") == "COMPILED"
        ]
        if len(compiled) != 1:
            raise RailRefused("BUNDLE_INVALID", 409)
        receipt = compiled[0]
        occurred_at = receipt.get("occurred_at")
        receipt_sha256 = receipt.get("receipt_sha256")
        payload = receipt.get("payload")
        if (
            type(occurred_at) is not str
            or type(receipt_sha256) is not str
            or not _SHA256_RE.fullmatch(receipt_sha256)
            or type(payload) is not dict
            or payload.get("source_sha256") != bundle_sha256
        ):
            raise RailRefused("BUNDLE_INVALID", 409)
        _parse_utc(occurred_at)
        return occurred_at, receipt_sha256

    @staticmethod
    def _self_modifies(source: dict[str, Any], protected: tuple[str, ...]) -> bool:
        protected_set = frozenset(protected)

        def contains_protected(value: object) -> bool:
            if type(value) is str:
                return value in protected_set
            if type(value) is list:
                return any(contains_protected(item) for item in value)
            if type(value) is dict:
                return any(
                    contains_protected(key) or contains_protected(item)
                    for key, item in value.items()
                )
            return False

        actions = source.get("actions")
        return type(actions) is not list or any(
            type(action) is not dict or contains_protected(action) for action in actions
        )

    def inspect(self, bundle_id: str) -> dict[str, Any]:
        if type(bundle_id) is not str or not _ID_RE.fullmatch(bundle_id):
            raise RailRefused("BUNDLE_NOT_FOUND", 404)
        now = self._now()
        activation = self._activation_now(now)
        try:
            bundle = self._compiler.get_bundle(bundle_id)
            integrity = self._compiler.verify_bundle_integrity(bundle_id)
        except RailRefused:
            raise
        except Exception:
            raise RailRefused("BUNDLE_INVALID", 409) from None
        if type(bundle) is not dict or type(integrity) is not dict:
            raise RailRefused("BUNDLE_INVALID", 409)
        source = bundle.get("source")
        if type(source) is not dict or source.get("bundle_id") != bundle_id:
            raise RailRefused("BUNDLE_INVALID", 409)
        digest = bundle.get("canonical_sha256")
        rev = bundle.get("rev")
        status = bundle.get("status")
        if (
            type(digest) is not str
            or not _SHA256_RE.fullmatch(digest)
            or type(rev) is not int
            or isinstance(rev, bool)
            or type(status) is not str
            or source.get("canonical_sha256") != digest
            or integrity.get("integrity") != "VERIFIED"
            or integrity.get("bundle_sha256") != digest
            or integrity.get("rev") != rev
            or integrity.get("status") != status
        ):
            raise RailRefused("BUNDLE_INVALID", 409)
        expires = _parse_utc(bundle.get("expires_at"))
        review = source.get("independent_review")
        policy = source.get("approval_policy")
        actions = source.get("actions")
        reason = "ELIGIBLE"
        if not activation.active:
            reason = activation.reason_code
        elif status in _TERMINAL_STATUSES or status != "DRAFT":
            reason = "ALREADY_DECIDED"
        elif now >= expires:
            reason = "BUNDLE_EXPIRED"
        elif (
            type(review) is not dict
            or review.get("verdict") != "SHIP-INERTLY"
            or type(review.get("artifact_sha256")) is not str
            or not _SHA256_RE.fullmatch(review["artifact_sha256"])
        ):
            reason = "INDEPENDENT_REVIEW_INVALID"
        elif (
            type(policy) is not dict
            or policy.get("approver_identity") != OWNER_IDENTITY
            or policy.get("approver_class") != OWNER_CLASS
        ):
            reason = "OWNER_POLICY_MISMATCH"
        elif type(actions) is not list or not actions:
            reason = "BUNDLE_INCOMPLETE"
        elif self._self_modifies(source, PROTECTED_AUTHORITY_IDS):
            reason = "CONTROL_PLANE_SELF_MODIFICATION"
        compiled_at, compile_receipt_sha256 = self._compile_evidence(
            bundle_id,
            digest,
        )

        safe_actions: list[dict[str, Any]] = []
        if type(actions) is list:
            for action in actions:
                if type(action) is not dict:
                    continue
                safe_action = {
                    field: action.get(field) for field in DISPLAY_ACTION_FIELDS
                }
                financial = action.get("financial")
                safe_action["financial"] = (
                    {field: financial.get(field) for field in DISPLAY_FINANCIAL_FIELDS}
                    if type(financial) is dict
                    else None
                )
                safe_actions.append(safe_action)
        dto: dict[str, Any] = {
            "schema_version": DISPLAY_SCHEMA,
            "bundle_id": bundle_id,
            "canonical_sha256": digest,
            "rev": rev,
            "status": status,
            "created_at": bundle.get("created_at"),
            "compiled_at": compiled_at,
            "compile_receipt_sha256": compile_receipt_sha256,
            "expires_at": bundle.get("expires_at"),
            "server_time": _utc(now),
            "creator": source.get("creator"),
            "purpose_class": source.get("purpose_class"),
            "scope": {
                field: source.get("scope", {}).get(field)
                for field in ("environment", "account", "destination")
            },
            "actions": safe_actions,
            "execution_policy": {
                field: source.get("execution_policy", {}).get(field)
                for field in ("failure_mode", "atomic_groups")
            },
            "partial_outcome_semantics": (
                "Independent groups may end PARTIAL; completed groups are never retried."
                if source.get("execution_policy", {}).get("failure_mode")
                == "INDEPENDENT_GROUPS"
                else "HALT_ALL stops later actions after the first failed group."
            ),
            "independent_review": {
                field: review.get(field) if type(review) is dict else None
                for field in DISPLAY_REVIEW_FIELDS
            },
            "approval_statement": source.get("approval_statement"),
            "approval_policy": {
                field: policy.get(field) if type(policy) is dict else None
                for field in ("approver_identity", "approver_class")
            },
            "dependency_pins": {
                "pin_set_sha256": PIN_SET_SHA256,
                "compiler_candidate_commit": DEPENDENCY_PINS[
                    "task053_candidate_commit"
                ],
                "compiler_candidate_tree": DEPENDENCY_PINS["task053_candidate_tree"],
                "compiler_result_sha256": DEPENDENCY_PINS["task053_result_sha256"],
                "compiler_review_sha256": DEPENDENCY_PINS["task053_review_sha256"],
                "fleet_lease_commit": DEPENDENCY_PINS["fleet_lease_runtime_commit"],
                "fleet_lease_tree": DEPENDENCY_PINS["fleet_lease_runtime_tree"],
                "fleet_lease_result_sha256": DEPENDENCY_PINS["task061_result_sha256"],
                "fleet_lease_review_sha256": DEPENDENCY_PINS["task061_review_sha256"],
                "fleet_lease_version": DEPENDENCY_PINS["fleet_lease_version"],
                "approval_schema_version": DEPENDENCY_PINS["approval_schema_version"],
                "approval_source_sha256": DEPENDENCY_PINS["approval_source_sha256"],
                "fleet_core_source_sha256": DEPENDENCY_PINS["fleet_core_source_sha256"],
                "approval_harness_commit": DEPENDENCY_PINS[
                    "approval_harness_merged_commit"
                ],
                "approval_harness_tree": DEPENDENCY_PINS[
                    "approval_harness_merged_tree"
                ],
                "consumer_commit": DEPENDENCY_PINS["task059_merged_commit"],
                "consumer_tree": DEPENDENCY_PINS["task059_merged_tree"],
                "consumer_result_sha256": DEPENDENCY_PINS["task059_result_sha256"],
                "consumer_review_sha256": DEPENDENCY_PINS["task059_review_sha256"],
                "consumer_source_sha256": DEPENDENCY_PINS[
                    "approval_consumer_source_sha256"
                ],
                "production_execution_available": DEPENDENCY_PINS[
                    "production_execution_available"
                ],
            },
            "eligibility": {"eligible": reason == "ELIGIBLE", "reason_code": reason},
            "consumer_state": "DISARMED",
        }
        dto["etag"] = canonical_sha256(dto)
        return dto

    def _connection(self) -> sqlite3.Connection:
        parent = self._session_registry_path.parent
        if (
            not parent.is_dir()
            or parent.is_symlink()
            or self._session_registry_path.parent.resolve(strict=True) != parent
            or self._session_registry_path == CANONICAL_REGISTRY_PATH
        ):
            raise RailRefused("SESSION_REGISTRY_INVALID", 503)
        try:
            descriptor = os.open(
                self._session_registry_path,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
        except FileExistsError:
            descriptor = -1
        except OSError:
            raise RailRefused("SESSION_REGISTRY_INVALID", 503) from None
        if descriptor >= 0:
            os.close(descriptor)
        if not _owner_private_file(self._session_registry_path):
            raise RailRefused("SESSION_REGISTRY_INVALID", 503)
        before = self._session_registry_path.stat()
        try:
            connection = sqlite3.connect(self._session_registry_path, timeout=10)
            database_path = connection.execute("PRAGMA database_list").fetchone()[2]
            after = self._session_registry_path.stat()
            if (
                Path(database_path).resolve(strict=True) != self._session_registry_path
                or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or not _owner_private_file(self._session_registry_path)
            ):
                connection.close()
                raise RailRefused("SESSION_REGISTRY_INVALID", 503)
        except RailRefused:
            raise
        except (OSError, sqlite3.Error, IndexError, TypeError):
            raise RailRefused("SESSION_REGISTRY_INVALID", 503) from None
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(_RAIL_SCHEMA)
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(owner_approval_rail_challenges)"
            )
        }
        if "challenge_attestation_sha256" not in columns:
            connection.execute(
                """
                ALTER TABLE owner_approval_rail_challenges
                ADD COLUMN challenge_attestation_sha256 TEXT NOT NULL DEFAULT ''
                """
            )

    def reauthenticate(self, bundle_id: str, owner: str) -> ChallengeIssue:
        if type(owner) is not str or owner != OWNER_IDENTITY:
            raise RailRefused("OWNER_MISMATCH", 403)
        dto = self.inspect(bundle_id)
        if not dto["eligibility"]["eligible"]:
            raise RailRefused(dto["eligibility"]["reason_code"])
        now = self._now()
        expires = min(
            now + timedelta(seconds=MAX_CHALLENGE_SECONDS),
            _parse_utc(dto["expires_at"]),
        )
        session = _opaque(32, self._token_bytes)
        csrf = _opaque(32, self._token_bytes)
        challenge_id = _opaque(32, self._token_bytes)
        session_hash = _secret_hash("session", session)
        csrf_hash = _secret_hash("csrf", csrf)
        challenge_hash = _secret_hash("challenge", challenge_id)
        statement_hash = hashlib.sha256(
            dto["approval_statement"].encode("utf-8")
        ).hexdigest()
        activation = self._activation_now(now)
        receipt_content = {
            "schema_version": RECEIPT_SCHEMA,
            "challenge_sha256": challenge_hash,
            "bundle_sha256": dto["canonical_sha256"],
            "statement_sha256": statement_hash,
            "approver_identity": owner,
            "approver_class": OWNER_CLASS,
            "issued_at": _utc(now),
            "expires_at": _utc(expires),
        }
        challenge_mac = self._challenge_attestor(receipt_content)
        if (
            type(challenge_mac) is not str
            or not _SHA256_RE.fullmatch(challenge_mac)
            or challenge_mac == "0" * 64
        ):
            raise RailRefused("CHALLENGE_AUTHORITY_INVALID", 503)
        with self._connection() as connection:
            self._ensure_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            deciding = connection.execute(
                """
                SELECT 1 FROM owner_approval_rail_challenges
                WHERE bundle_id = ? AND owner_identity = ? AND state = 'DECIDING'
                """,
                (bundle_id, owner),
            ).fetchone()
            if deciding is not None:
                raise RailRefused("DECISION_IN_PROGRESS")
            connection.execute(
                """
                UPDATE owner_approval_rail_challenges
                SET state = 'SUPERSEDED'
                WHERE bundle_id = ? AND owner_identity = ? AND state = 'PENDING'
                """,
                (bundle_id, owner),
            )
            connection.execute(
                """
                INSERT INTO owner_approval_rail_challenges (
                    challenge_sha256, session_sha256, csrf_sha256,
                    owner_identity, bundle_id, bundle_sha256, expected_rev,
                    statement_sha256, pin_set_sha256,
                    registry_identity_sha256, challenge_attestation_sha256,
                    issued_at, expires_at, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    challenge_hash,
                    session_hash,
                    csrf_hash,
                    owner,
                    bundle_id,
                    dto["canonical_sha256"],
                    dto["rev"],
                    statement_hash,
                    activation.pin_set_sha256,
                    activation.registry_identity_sha256,
                    challenge_mac,
                    _utc(now),
                    _utc(expires),
                ),
            )
        return ChallengeIssue(session, csrf, _utc(expires))

    def _challenge(self, session_cookie: str) -> sqlite3.Row:
        session_hash = _secret_hash("session", session_cookie)
        with self._connection() as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                "SELECT * FROM owner_approval_rail_challenges WHERE session_sha256 = ?",
                (session_hash,),
            ).fetchone()
        if row is None:
            raise RailRefused("SESSION_INVALID", 403)
        return row

    def _provision_receipt(
        self,
        *,
        challenge: sqlite3.Row,
    ) -> str:
        receipt_content = {
            "schema_version": RECEIPT_SCHEMA,
            "challenge_sha256": challenge["challenge_sha256"],
            "bundle_sha256": challenge["bundle_sha256"],
            "statement_sha256": challenge["statement_sha256"],
            "approver_identity": challenge["owner_identity"],
            "approver_class": OWNER_CLASS,
            "issued_at": challenge["issued_at"],
            "expires_at": challenge["expires_at"],
            "challenge_attestation_sha256": challenge["challenge_attestation_sha256"],
        }
        with self._connection() as connection:
            self._ensure_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            live = connection.execute(
                "SELECT * FROM owner_approval_rail_challenges WHERE challenge_sha256 = ?",
                (challenge["challenge_sha256"],),
            ).fetchone()
            if live is None or live["state"] != "DECIDING":
                raise RailRefused("CHALLENGE_INVALID")
        try:
            return self._compiler.provision_attended_approval_receipt(
                receipt_content,
                operation_key=("attended-provision-" + challenge["challenge_sha256"]),
            )
        except Exception:
            raise RailRefused("ATTENDED_RECEIPT_REFUSED") from None

    def decide(
        self,
        bundle_id: str,
        *,
        owner: str,
        session_cookie: str,
        csrf_challenge: str,
        decision: str,
        canonical_sha256: str,
        expected_rev: int,
    ) -> dict[str, Any]:
        if type(owner) is not str or owner != OWNER_IDENTITY:
            raise RailRefused("OWNER_MISMATCH", 403)
        if type(session_cookie) is not str:
            raise RailRefused("SESSION_INVALID", 403)
        if type(csrf_challenge) is not str:
            raise RailRefused("CSRF_INVALID", 403)
        if type(decision) is not str or decision not in {"APPROVE", "REFUSE"}:
            raise RailRefused("DECISION_INVALID", 422)
        if (
            type(canonical_sha256) is not str
            or not _SHA256_RE.fullmatch(canonical_sha256)
            or type(expected_rev) is not int
            or isinstance(expected_rev, bool)
        ):
            raise RailRefused("BUNDLE_CHANGED")
        now = self._now()
        activation = self._activation_now(now)
        if not activation.active:
            raise RailRefused(activation.reason_code)
        challenge = self._challenge(session_cookie)
        if challenge["owner_identity"] != owner or challenge["bundle_id"] != bundle_id:
            raise RailRefused("OWNER_MISMATCH", 403)
        if challenge["state"] == "SUPERSEDED":
            raise RailRefused("CHALLENGE_SUPERSEDED")
        if challenge["state"] == "TERMINAL":
            if (
                challenge["decision"] == decision
                and challenge["bundle_sha256"] == canonical_sha256
                and challenge["expected_rev"] == expected_rev
                and hmac.compare_digest(
                    challenge["csrf_sha256"], _secret_hash("csrf", csrf_challenge)
                )
            ):
                return json.loads(challenge["result_json"])
            raise RailRefused("CHALLENGE_USED")
        if now >= _parse_utc(challenge["expires_at"]):
            raise RailRefused("CHALLENGE_EXPIRED")
        if not hmac.compare_digest(
            challenge["csrf_sha256"], _secret_hash("csrf", csrf_challenge)
        ):
            raise RailRefused("CSRF_INVALID", 403)
        if (
            challenge["bundle_sha256"] != canonical_sha256
            or challenge["expected_rev"] != expected_rev
            or challenge["pin_set_sha256"] != activation.pin_set_sha256
            or challenge["registry_identity_sha256"]
            != activation.registry_identity_sha256
        ):
            raise RailRefused("BUNDLE_CHANGED")
        if challenge["state"] == "PENDING":
            current_view = self.inspect(bundle_id)
            if (
                not current_view["eligibility"]["eligible"]
                or current_view["canonical_sha256"] != canonical_sha256
                or current_view["rev"] != expected_rev
                or hashlib.sha256(
                    current_view["approval_statement"].encode("utf-8")
                ).hexdigest()
                != challenge["statement_sha256"]
            ):
                raise RailRefused("BUNDLE_CHANGED")
        operation_key = (
            "rail-"
            + hashlib.sha256(
                canonical_json(
                    {
                        "schema_version": CHALLENGE_SCHEMA,
                        "challenge_sha256": challenge["challenge_sha256"],
                        "bundle_sha256": canonical_sha256,
                        "expected_rev": expected_rev,
                        "decision": decision,
                    }
                ).encode("utf-8")
            ).hexdigest()
        )
        with self._connection() as connection:
            self._ensure_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT * FROM owner_approval_rail_challenges WHERE challenge_sha256 = ?",
                (challenge["challenge_sha256"],),
            ).fetchone()
            if (
                current["state"] == "TERMINAL"
                and current["decision"] == decision
                and current["operation_key"] == operation_key
                and type(current["result_json"]) is str
            ):
                return json.loads(current["result_json"])
            if current["state"] == "PENDING":
                changed = connection.execute(
                    """
                    UPDATE owner_approval_rail_challenges
                    SET state = 'DECIDING', decision = ?, operation_key = ?
                    WHERE challenge_sha256 = ? AND state = 'PENDING'
                    """,
                    (decision, operation_key, challenge["challenge_sha256"]),
                ).rowcount
                if changed != 1:
                    raise RailRefused("DECISION_RACE")
            elif (
                current["state"] != "DECIDING"
                or current["decision"] != decision
                or current["operation_key"] != operation_key
            ):
                raise RailRefused("CHALLENGE_USED")
        bundle = self._compiler.get_bundle(bundle_id)
        source = bundle["source"]
        statement = source["approval_statement"]
        if (
            bundle["canonical_sha256"] != canonical_sha256
            or hashlib.sha256(statement.encode("utf-8")).hexdigest()
            != challenge["statement_sha256"]
        ):
            raise RailRefused("BUNDLE_CHANGED")
        if decision == "APPROVE":
            try:
                receipt_sha = self._provision_receipt(
                    challenge=challenge,
                )
            except RailRefused as exc:
                replay = self._challenge(session_cookie)
                if (
                    exc.code == "CHALLENGE_INVALID"
                    and replay["state"] == "TERMINAL"
                    and replay["decision"] == decision
                    and replay["operation_key"] == operation_key
                    and type(replay["result_json"]) is str
                ):
                    return json.loads(replay["result_json"])
                raise
            decided = self._compiler.approve_bundle(
                bundle_id,
                bundle_sha256=canonical_sha256,
                expected_rev=expected_rev,
                approval_statement=statement,
                attended_receipt_sha256=receipt_sha,
                actor=owner,
                operation_key=operation_key,
            )
            message = "Approval recorded. Nothing executed. Consumer remains disarmed."
        else:
            decided = self._compiler.revoke_bundle(
                bundle_id,
                bundle_sha256=canonical_sha256,
                expected_rev=expected_rev,
                reason="OWNER_REFUSED",
                actor=owner,
                operation_key=operation_key,
            )
            message = "Refusal recorded. Nothing executed. Consumer remains disarmed."
        result = {
            "schema_version": "owner-approval-result/v1",
            "bundle_id": bundle_id,
            "canonical_sha256": canonical_sha256,
            "rev": decided["rev"],
            "status": decided["status"],
            "decision": decision,
            "recorded_at": _utc(self._now()),
            "message": message,
            "consumer_state": "DISARMED",
        }
        encoded = canonical_json(result)
        with self._connection() as connection:
            self._ensure_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            final = connection.execute(
                """
                SELECT state, decision, operation_key, result_json
                FROM owner_approval_rail_challenges
                WHERE challenge_sha256 = ?
                """,
                (challenge["challenge_sha256"],),
            ).fetchone()
            if (
                final is not None
                and final["state"] == "TERMINAL"
                and final["decision"] == decision
                and final["operation_key"] == operation_key
                and final["result_json"] == encoded
            ):
                return json.loads(final["result_json"])
            if final is None or final["state"] != "DECIDING":
                raise RailRefused("DECISION_RACE")
            connection.execute(
                """
                UPDATE owner_approval_rail_challenges
                SET state = 'TERMINAL', result_json = ?
                WHERE challenge_sha256 = ? AND state = 'DECIDING'
                """,
                (encoded, challenge["challenge_sha256"]),
            )
        return result


def _host_ip(host_header: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if type(host_header) is not str:
        return None
    host = host_header
    if host.startswith("["):
        closing = host.find("]")
        if closing < 0:
            return None
        host = host[1:closing]
    elif host.count(":") == 1:
        host = host.partition(":")[0]
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def local_context_reason(
    peer_host: str,
    host_header: str,
    environment: Mapping[str, str],
    containerized: bool,
) -> str | None:
    if any(environment.get(marker) for marker in _CLOUD_MARKERS):
        return "CLOUD_RUNTIME"
    if containerized:
        return "CONTAINER_RUNTIME"
    try:
        peer = ipaddress.ip_address(peer_host)
    except ValueError:
        return "NON_LOOPBACK_PEER"
    host = _host_ip(host_header)
    if not peer.is_loopback:
        return "NON_LOOPBACK_PEER"
    if host is None or not host.is_loopback:
        return "NON_LOOPBACK_HOST"
    return None


def _containerized() -> bool:
    return bool(
        os.environ.get("CONTAINER")
        or os.environ.get("DOCKER_CONTAINER")
        or Path("/.dockerenv").exists()
    )


_PRIVATE_HEADERS = {
    "Cache-Control": "no-store, private",
    "Pragma": "no-cache",
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; img-src 'self'; "
        "style-src 'self'; script-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class ReauthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decision: str
    canonical_sha256: str
    expected_rev: int
    csrf_challenge: str


def create_owner_approval_router(
    rail: OwnerApprovalRail,
    *,
    authenticate: Callable[[str, str], str],
    asset_dir: Path,
    containerized: Callable[[], bool] = _containerized,
) -> APIRouter:
    """Create the isolated route set; the public dashboard remains unchanged."""
    router = APIRouter()
    basic = HTTPBasic(auto_error=False)

    def refusal(exc: RailRefused) -> HTTPException:
        headers = dict(_PRIVATE_HEADERS)
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Basic"
        return HTTPException(
            status_code=exc.status_code,
            detail=exc.code,
            headers=headers,
        )

    def local_owner(
        request: Request,
        credentials: HTTPBasicCredentials | None = Depends(basic),
    ) -> str:
        peer = request.client.host if request.client is not None else ""
        reason = local_context_reason(
            peer,
            request.headers.get("host", ""),
            os.environ,
            containerized(),
        )
        if reason is not None:
            raise HTTPException(status_code=404, detail="not found")
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Basic", **_PRIVATE_HEADERS},
            )
        try:
            owner = authenticate(credentials.username, credentials.password)
        except RailRefused as exc:
            raise refusal(exc) from None
        if owner != OWNER_IDENTITY:
            raise HTTPException(
                status_code=403, detail="owner required", headers=_PRIVATE_HEADERS
            )
        return owner

    def mutation_boundary(request: Request) -> None:
        content_type = (
            request.headers.get("content-type", "").partition(";")[0].strip().lower()
        )
        host = request.headers.get("host", "")
        origin = request.headers.get("origin", "")
        fetch_site = request.headers.get("sec-fetch-site")
        if content_type != "application/json":
            raise HTTPException(
                status_code=415, detail="JSON_REQUIRED", headers=_PRIVATE_HEADERS
            )
        if request.url.scheme != "https" or origin != f"https://{host}":
            raise HTTPException(
                status_code=403, detail="ORIGIN_INVALID", headers=_PRIVATE_HEADERS
            )
        if fetch_site is not None and fetch_site != "same-origin":
            raise HTTPException(
                status_code=403, detail="FETCH_SITE_INVALID", headers=_PRIVATE_HEADERS
            )

    async def validated_body(
        request: Request,
        model: type[BaseModel],
    ) -> BaseModel:
        mutation_boundary(request)
        try:
            raw = await request.body()
            if len(raw) > 4096:
                raise ValueError

            def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
                value: dict[str, Any] = {}
                for key, item in items:
                    if key in value:
                        raise ValueError
                    value[key] = item
                return value

            document = json.loads(
                raw.decode("utf-8", "strict"),
                object_pairs_hook=pairs,
            )
            return model.model_validate(document)
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="REQUEST_SHAPE_INVALID",
                headers=_PRIVATE_HEADERS,
            ) from None

    def require_policy_owner(dto: dict[str, Any], owner: str) -> None:
        if dto["approval_policy"]["approver_identity"] != owner:
            raise HTTPException(
                status_code=403, detail="owner required", headers=_PRIVATE_HEADERS
            )

    @router.get("/api/operator/v1/approval-bundles/{bundle_id}")
    def inspect_bundle(bundle_id: str, owner: str = Depends(local_owner)) -> Response:
        try:
            dto = rail.inspect(bundle_id)
        except RailRefused as exc:
            raise refusal(exc) from None
        require_policy_owner(dto, owner)
        return Response(
            canonical_json(dto),
            media_type="application/json",
            headers={**_PRIVATE_HEADERS, "ETag": f'"{dto["etag"]}"'},
        )

    @router.post("/api/operator/v1/approval-bundles/{bundle_id}/reauth")
    async def reauthenticate(
        bundle_id: str,
        request: Request,
        response: Response,
        owner: str = Depends(local_owner),
    ) -> dict[str, str]:
        await validated_body(request, ReauthRequest)
        try:
            dto = rail.inspect(bundle_id)
            require_policy_owner(dto, owner)
            issued = rail.reauthenticate(bundle_id, owner)
        except RailRefused as exc:
            raise refusal(exc) from None
        for name, value in _PRIVATE_HEADERS.items():
            response.headers[name] = value
        response.set_cookie(
            SESSION_COOKIE,
            issued.session_cookie,
            max_age=MAX_CHALLENGE_SECONDS,
            secure=True,
            httponly=True,
            samesite="strict",
            path=f"/api/operator/v1/approval-bundles/{bundle_id}",
        )
        return {
            "csrf_challenge": issued.csrf_challenge,
            "expires_at": issued.expires_at,
        }

    @router.post("/api/operator/v1/approval-bundles/{bundle_id}/decision")
    async def decide(
        bundle_id: str,
        request: Request,
        response: Response,
        owner: str = Depends(local_owner),
        session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    ) -> dict[str, Any]:
        body = await validated_body(request, DecisionRequest)
        assert isinstance(body, DecisionRequest)
        if session_cookie is None:
            raise HTTPException(
                status_code=403, detail="SESSION_INVALID", headers=_PRIVATE_HEADERS
            )
        try:
            result = rail.decide(
                bundle_id,
                owner=owner,
                session_cookie=session_cookie,
                csrf_challenge=body.csrf_challenge,
                decision=body.decision,
                canonical_sha256=body.canonical_sha256,
                expected_rev=body.expected_rev,
            )
        except RailRefused as exc:
            raise refusal(exc) from None
        for name, value in _PRIVATE_HEADERS.items():
            response.headers[name] = value
        response.delete_cookie(
            SESSION_COOKIE,
            path=f"/api/operator/v1/approval-bundles/{bundle_id}",
            secure=True,
            httponly=True,
            samesite="strict",
        )
        return result

    @router.get("/operator/approvals/{bundle_id}", response_class=FileResponse)
    def approval_page(bundle_id: str, owner: str = Depends(local_owner)) -> Response:
        try:
            dto = rail.inspect(bundle_id)
        except RailRefused as exc:
            raise refusal(exc) from None
        require_policy_owner(dto, owner)
        page = asset_dir / "approval.html"
        if not page.is_file():
            raise HTTPException(status_code=503, detail="approval surface not built")
        return FileResponse(
            page,
            media_type="text/html; charset=utf-8",
            headers=_PRIVATE_HEADERS,
        )

    return router


def production_rail() -> OwnerApprovalRail:
    """Build the fixed-path local profile. It creates no file or schema."""
    challenge_authority = ChallengeMacAuthority(ACTIVATION_KEY_PATH)
    compiler = FleetLeaseCompilerPort(
        challenge_verifier=challenge_authority.verify,
    )
    verifier = ActivationVerifier(
        registry_path=CANONICAL_REGISTRY_PATH,
        attestation_path=ACTIVATION_PATH,
        key_path=ACTIVATION_KEY_PATH,
        consume_legacy_receipt=compiler.consume_legacy_owner_activation,
    )
    return OwnerApprovalRail(
        compiler=compiler,
        activation=verifier.verify,
        clock=lambda: datetime.now(UTC),
        token_bytes=os.urandom,
        session_registry_path=SESSION_REGISTRY_PATH,
        challenge_attestor=challenge_authority.attest,
    )


__all__ = [
    "ACTIVATION_SCHEMA",
    "ActivationState",
    "ActivationVerifier",
    "CANONICAL_REGISTRY_PATH",
    "ChallengeMacAuthority",
    "ChallengeIssue",
    "DEPENDENCY_PINS",
    "DISPLAY_SCHEMA",
    "MAX_CHALLENGE_SECONDS",
    "OWNER_IDENTITY",
    "OwnerApprovalRail",
    "PIN_SET_SHA256",
    "RailRefused",
    "canonical_json",
    "canonical_sha256",
    "create_owner_approval_router",
    "local_context_reason",
    "production_rail",
    "registry_identity_sha256",
]

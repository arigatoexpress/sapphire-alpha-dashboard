"""Golden and hostile tests for the local owner approval rail.

All lifecycle writes use a temporary registry and a fake of the installed
public fleet-lease API. No live bundle, receipt, credential, connector, or
external action is touched.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from owner_approval import (
    ACTIVATION_SCHEMA,
    DISPLAY_ACTION_FIELDS,
    DISPLAY_FINANCIAL_FIELDS,
    DISPLAY_REVIEW_FIELDS,
    PIN_SET_SHA256,
    PROTECTED_AUTHORITY_IDS,
    ActivationState,
    ActivationVerifier,
    ChallengeMacAuthority,
    FleetLeaseCompilerPort,
    OwnerApprovalRail,
    RailRefused,
    canonical_json,
    create_owner_approval_router,
    local_context_reason,
    registry_identity_sha256,
)


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
OWNER = "ari"
PASSWORD = "owner-test-password-99"
BUNDLE_ID = "approval-20260728-risk-trim"
BUNDLE_SHA = hashlib.sha256(b"exact-reviewed-bundle").hexdigest()
PROTECTED_SERVICE = PROTECTED_AUTHORITY_IDS[0]
CHALLENGE_KEY = b"copied-owner-session-key-material"


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _challenge_mac(content: dict) -> str:
    return hmac.new(
        CHALLENGE_KEY,
        b"owner-approval-session-challenge/v1\0"
        + canonical_json(content).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _action(action_id: str = "trim-edge", *, service: str | None = None) -> dict:
    parameters = [
        {
            "name": "reason_code",
            "value": "reason:" + hashlib.sha256(b"risk-reduction").hexdigest(),
            "unit": "reason-id",
        }
    ]
    kind = "FINANCIAL"
    if service is not None:
        kind = "DEPLOYMENT"
        parameters = [
            {"name": "service", "value": service, "unit": "service-id"},
            {
                "name": "region",
                "value": "region:" + hashlib.sha256(b"us-central1").hexdigest(),
                "unit": "region-id",
            },
            {"name": "traffic_percent", "value": 100, "unit": "percent"},
        ]
    return {
        "action_id": action_id,
        "action_kind": kind,
        "atomic_group": f"group-{action_id}",
        "environment": "env:" + hashlib.sha256(b"personal").hexdigest(),
        "account": "acct:" + hashlib.sha256(b"agentic").hexdigest(),
        "destination": "dest:" + hashlib.sha256(b"bounded").hexdigest(),
        "parameters": parameters,
        "units": "SHARE" if kind == "FINANCIAL" else "TRAFFIC_PERCENT",
        "max_cost": {"amount_minor": 2500, "currency": "USD", "scale": 2},
        "max_slippage_bps": 20 if kind == "FINANCIAL" else 0,
        "target_revision_sha256": hashlib.sha256(action_id.encode()).hexdigest(),
        "idempotency_key": f"{action_id}-one-use",
        "preconditions": ["quote is current", "position is sufficient"],
        "expected_effects": ["reduce exactly one encoded position"],
        "verification": ["receipt matches the exact action digest"],
        "rollback": ["cancellation requires a new exact authority"],
        "kill_switch": "pause before any changed action",
        "residual_risks": ["market can move before external execution"],
        "financial": (
            {
                "account": "acct:" + hashlib.sha256(b"agentic").hexdigest(),
                "symbol": "symbol:" + hashlib.sha256(b"edge-option").hexdigest(),
                "asset": "asset:" + hashlib.sha256(b"option").hexdigest(),
                "side": "SELL",
                "quantity": {"value": 1, "unit": "CONTRACT"},
                "max_notional": None,
                "order_type": "LIMIT",
                "limit_price": {
                    "amount_minor": 2500,
                    "currency": "USD",
                    "scale": 2,
                },
                "stop_price": None,
                "time_in_force": "DAY",
                "estimated_fees": {
                    "amount_minor": 0,
                    "currency": "USD",
                    "scale": 2,
                },
                "max_slippage_bps": 20,
                "market_hours_policy": "REGULAR_ONLY",
            }
            if kind == "FINANCIAL"
            else None
        ),
    }


def _bundle(
    *,
    status: str = "DRAFT",
    expires_at: datetime | None = None,
    actions: list[dict] | None = None,
) -> dict:
    source = {
        "schema_version": "3.0.0",
        "bundle_id": BUNDLE_ID,
        "canonical_sha256": BUNDLE_SHA,
        "created_at": _utc(NOW - timedelta(minutes=2)),
        "expires_at": _utc(expires_at or NOW + timedelta(minutes=10)),
        "creator": "codex-approval-bundle",
        "purpose_class": "RISK_REDUCTION",
        "scope": {
            "environment": "env:" + hashlib.sha256(b"personal").hexdigest(),
            "account": "acct:" + hashlib.sha256(b"agentic").hexdigest(),
            "destination": "dest:" + hashlib.sha256(b"bounded").hexdigest(),
        },
        "actions": actions or [_action("first"), _action("second")],
        "execution_policy": {
            "failure_mode": "INDEPENDENT_GROUPS",
            "atomic_groups": ["group-first", "group-second"],
        },
        "independent_review": {
            "reviewer": "codex-independent",
            "reviewer_class": "INDEPENDENT_AGENT",
            "verdict": "SHIP-INERTLY",
            "reviewed_at": _utc(NOW - timedelta(minutes=1)),
            "candidate_sha256": hashlib.sha256(b"candidate").hexdigest(),
            "artifact_sha256": hashlib.sha256(b"review").hexdigest(),
        },
        "approval_statement": (
            f"APPROVE {BUNDLE_ID} SHA256 {BUNDLE_SHA} UNTIL "
            f"{_utc(expires_at or NOW + timedelta(minutes=10))} ACTIONS "
            f"{len(actions or [_action('first'), _action('second')])}. "
            "NO CHANGED OR FUTURE ACTIONS ARE AUTHORIZED; APPROVAL IS NOT EXECUTION."
        ),
        "approval_policy": {
            "approver_identity": OWNER,
            "approver_class": "HUMAN_ATTENDED",
        },
        "lifecycle": "DRAFT",
    }
    return {
        "bundle_id": BUNDLE_ID,
        "rev": 1,
        "canonical_sha256": BUNDLE_SHA,
        "schema_version": "3.0.0",
        "created_at": source["created_at"],
        "expires_at": source["expires_at"],
        "creator": source["creator"],
        "purpose": source["purpose_class"],
        "status": status,
        "updated_at": source["created_at"],
        "source": source,
    }


class FakeCompiler:
    """Public-lifecycle fake; it records authority but never executes it."""

    def __init__(
        self,
        bundle: dict,
        registry: Path,
        *,
        approve_fail_once: str | None = None,
    ):
        self.bundle = json.loads(json.dumps(bundle))
        self.registry = registry
        self.approve_calls: list[dict] = []
        self.revoke_calls: list[dict] = []
        self._lock = threading.Lock()
        self._replays: dict[str, dict] = {}
        self.approve_fail_once = approve_fail_once
        self.provisioned_receipts: dict[str, dict] = {}
        self.consumed_receipts: set[str] = set()

    def get_bundle(self, bundle_id: str) -> dict:
        if bundle_id != self.bundle["bundle_id"]:
            raise RailRefused("BUNDLE_NOT_FOUND", 404)
        return json.loads(json.dumps(self.bundle))

    def verify_bundle_integrity(self, bundle_id: str) -> dict:
        bundle = self.get_bundle(bundle_id)
        return {
            "integrity": "VERIFIED",
            "bundle_sha256": bundle["canonical_sha256"],
            "rev": bundle["rev"],
            "status": bundle["status"],
            "receipt_count": 1,
        }

    def bundle_receipts(self, bundle_id: str) -> list[dict]:
        bundle = self.get_bundle(bundle_id)
        return [
            {
                "event_type": "COMPILED",
                "occurred_at": _utc(NOW - timedelta(seconds=30)),
                "receipt_sha256": hashlib.sha256(b"compile-receipt").hexdigest(),
                "payload": {"source_sha256": bundle["canonical_sha256"]},
            }
        ]

    def provision_attended_approval_receipt(
        self,
        content: dict,
        *,
        operation_key: str,
    ) -> str:
        supplied_mac = content.get("challenge_attestation_sha256")
        unsigned = {
            key: value
            for key, value in content.items()
            if key != "challenge_attestation_sha256"
        }
        if type(supplied_mac) is not str or not hmac.compare_digest(
            supplied_mac, _challenge_mac(unsigned)
        ):
            raise RailRefused("ATTENDED_CHALLENGE_UNAUTHENTICATED")
        receipt_sha = hashlib.sha256(
            canonical_json(content).encode("utf-8")
        ).hexdigest()
        prior = self.provisioned_receipts.get(operation_key)
        if prior is not None and prior != content:
            raise RailRefused("ATTENDED_RECEIPT_REFUSED")
        if prior is None and any(
            item["bundle_sha256"] == content["bundle_sha256"]
            and sha not in self.consumed_receipts
            for sha, item in (
                (
                    hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest(),
                    value,
                )
                for value in self.provisioned_receipts.values()
            )
        ):
            raise RailRefused("ATTENDED_RECEIPT_REFUSED")
        self.provisioned_receipts[operation_key] = json.loads(json.dumps(content))
        return receipt_sha

    def consume_legacy_owner_activation(self, **kwargs: str) -> bool:
        return False

    def approve_bundle(self, bundle_id: str, **kwargs: object) -> dict:
        with self._lock:
            operation_key = str(kwargs["operation_key"])
            if operation_key in self._replays:
                return json.loads(json.dumps(self._replays[operation_key]))
            if self.approve_fail_once == "before":
                self.approve_fail_once = None
                raise RuntimeError("simulated crash before lifecycle write")
            assert bundle_id == self.bundle["bundle_id"]
            assert kwargs["bundle_sha256"] == self.bundle["canonical_sha256"]
            assert kwargs["expected_rev"] == self.bundle["rev"]
            assert (
                kwargs["approval_statement"]
                == self.bundle["source"]["approval_statement"]
            )
            assert kwargs["actor"] == OWNER
            receipt_sha = str(kwargs["attended_receipt_sha256"])
            assert any(
                hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
                == receipt_sha
                for value in self.provisioned_receipts.values()
            )
            assert receipt_sha not in self.consumed_receipts
            self.consumed_receipts.add(receipt_sha)
            self.approve_calls.append(dict(kwargs))
            self.bundle["status"] = "APPROVED"
            self.bundle["rev"] += 1
            self._replays[operation_key] = json.loads(json.dumps(self.bundle))
            if self.approve_fail_once == "after":
                self.approve_fail_once = None
                raise RuntimeError("simulated crash after lifecycle write")
            return json.loads(json.dumps(self.bundle))

    def revoke_bundle(self, bundle_id: str, **kwargs: object) -> dict:
        with self._lock:
            operation_key = str(kwargs["operation_key"])
            if operation_key in self._replays:
                return json.loads(json.dumps(self._replays[operation_key]))
            assert bundle_id == self.bundle["bundle_id"]
            assert kwargs["reason"] == "OWNER_REFUSED"
            assert kwargs["actor"] == OWNER
            self.revoke_calls.append(dict(kwargs))
            self.bundle["status"] = "REVOKED"
            self.bundle["rev"] += 1
            self._replays[operation_key] = json.loads(json.dumps(self.bundle))
            return json.loads(json.dumps(self.bundle))


def _initialize_registry(path: Path) -> None:
    sqlite3.connect(path).close()
    path.chmod(0o600)


def _active() -> ActivationState:
    return ActivationState(
        active=True,
        reason_code="ACTIVE",
        pin_set_sha256=PIN_SET_SHA256,
        registry_identity_sha256="a" * 64,
        protected_authority_ids=PROTECTED_AUTHORITY_IDS,
        expires_at=_utc(NOW + timedelta(hours=1)),
    )


@pytest.fixture
def rail(tmp_path: Path) -> tuple[OwnerApprovalRail, FakeCompiler, Path]:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    compiler = FakeCompiler(_bundle(), registry)
    counter = iter(range(1, 256))
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=lambda size: bytes([next(counter)]) * size,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    return instance, compiler, registry


def test_local_context_rejects_cloud_container_wildcard_and_remote() -> None:
    assert local_context_reason("127.0.0.1", "127.0.0.1:8099", {}, False) is None
    assert local_context_reason("203.0.113.4", "127.0.0.1:8099", {}, False) == (
        "NON_LOOPBACK_PEER"
    )
    assert local_context_reason("127.0.0.1", "0.0.0.0:8099", {}, False) == (
        "NON_LOOPBACK_HOST"
    )
    assert local_context_reason("127.0.0.1", "localhost:8099", {}, False) == (
        "NON_LOOPBACK_HOST"
    )
    assert local_context_reason(
        "127.0.0.1", "127.0.0.1:8099", {"K_SERVICE": "x"}, False
    ) == ("CLOUD_RUNTIME")
    assert local_context_reason("127.0.0.1", "127.0.0.1:8099", {}, True) == (
        "CONTAINER_RUNTIME"
    )


def test_activation_requires_owner_private_mac_and_exact_registry(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    key = tmp_path / "activation.key"
    key.write_bytes(b"k" * 32)
    key.chmod(0o600)
    attestation = tmp_path / "activation.json"
    issued = NOW - timedelta(minutes=1)
    payload = {
        "schema_version": ACTIVATION_SCHEMA,
        "scope": "LOCAL_OWNER_APPROVAL_RAIL",
        "pin_set_sha256": PIN_SET_SHA256,
        "registry_identity_sha256": registry_identity_sha256(registry),
        "legacy_gate_receipt_sha256": hashlib.sha256(b"legacy-gate").hexdigest(),
        "nonce_sha256": hashlib.sha256(b"one-use-nonce").hexdigest(),
        "issued_at": _utc(issued),
        "expires_at": _utc(NOW + timedelta(minutes=30)),
    }
    payload["mac_sha256"] = hmac.new(
        key.read_bytes(),
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    attestation.write_text(canonical_json(payload), encoding="utf-8")
    attestation.chmod(0o600)
    consumed: list[dict[str, str]] = []

    def consume(**kwargs: str) -> bool:
        consumed.append(kwargs)
        return kwargs["receipt_sha256"] == payload["legacy_gate_receipt_sha256"]

    verifier = ActivationVerifier(
        registry_path=registry,
        attestation_path=attestation,
        key_path=key,
        consume_legacy_receipt=consume,
    )
    state = verifier.verify(NOW)
    assert state.active is True
    assert state.protected_authority_ids == PROTECTED_AUTHORITY_IDS
    assert len(consumed) == 1

    phantom = ActivationVerifier(
        registry_path=registry,
        attestation_path=attestation,
        key_path=key,
        consume_legacy_receipt=lambda **_kwargs: False,
    )
    assert phantom.verify(NOW).reason_code == "LEGACY_RECEIPT_INVALID"

    payload["protected_authority_ids"] = []
    unsigned = {
        key_name: value
        for key_name, value in payload.items()
        if key_name != "mac_sha256"
    }
    payload["mac_sha256"] = hmac.new(
        key.read_bytes(),
        canonical_json(unsigned).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    attestation.write_text(canonical_json(payload), encoding="utf-8")
    assert verifier.verify(NOW).reason_code == "ACTIVATION_FILE_INVALID"
    payload.pop("protected_authority_ids")
    payload["mac_sha256"] = hmac.new(
        key.read_bytes(),
        canonical_json(
            {
                key_name: value
                for key_name, value in payload.items()
                if key_name != "mac_sha256"
            }
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    attestation.write_text(canonical_json(payload), encoding="utf-8")

    substituted_registry = tmp_path / "substituted.sqlite3"
    substituted_registry.write_bytes(registry.read_bytes())
    substituted_registry.chmod(0o600)
    substituted = ActivationVerifier(
        registry_path=substituted_registry,
        attestation_path=attestation,
        key_path=key,
        consume_legacy_receipt=consume,
    )
    assert substituted.verify(NOW).reason_code == "ACTIVATION_BINDING_INVALID"

    payload["mac_sha256"] = "f" * 64
    attestation.write_text(canonical_json(payload), encoding="utf-8")
    assert verifier.verify(NOW).reason_code == "ACTIVATION_MAC_INVALID"
    attestation.chmod(0o644)
    assert verifier.verify(NOW).reason_code == "ACTIVATION_FILE_INVALID"


def test_owner_session_challenge_attestation_is_exact_and_key_bound(
    tmp_path: Path,
) -> None:
    key = tmp_path / "activation.key"
    key.write_bytes(CHALLENGE_KEY)
    key.chmod(0o600)
    authority = ChallengeMacAuthority(key)
    content = {
        "schema_version": "attended-approval-receipt/v1",
        "challenge_id": "challenge-1",
        "bundle_id": BUNDLE_ID,
        "approval_statement": "Approve this exact immutable bundle.",
        "owner_identity": OWNER,
        "approver_class": "HUMAN",
        "issued_at": _utc(NOW),
        "expires_at": _utc(NOW + timedelta(minutes=5)),
    }

    attestation = authority.attest(content)
    assert authority.verify(content, attestation) is True
    assert authority.verify({**content, "bundle_id": "substituted"}, attestation) is False

    key.chmod(0o644)
    assert authority.verify(content, attestation) is False


def test_inspection_is_exact_ordered_and_read_only(rail) -> None:
    instance, compiler, registry = rail
    before = registry.read_bytes()
    dto = instance.inspect(BUNDLE_ID)
    assert dto["canonical_sha256"] == BUNDLE_SHA
    assert len(dto["canonical_sha256"]) == 64
    assert dto["rev"] == 1
    assert (
        dto["compile_receipt_sha256"] == hashlib.sha256(b"compile-receipt").hexdigest()
    )
    assert [action["action_id"] for action in dto["actions"]] == ["first", "second"]
    assert dto["execution_policy"]["failure_mode"] == "INDEPENDENT_GROUPS"
    assert dto["partial_outcome_semantics"]
    assert dto["approval_statement"] == compiler.bundle["source"]["approval_statement"]
    assert dto["eligibility"] == {"eligible": True, "reason_code": "ELIGIBLE"}
    assert dto["consumer_state"] == "DISARMED"
    assert registry.read_bytes() == before


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda compiler: compiler.bundle.update(status="APPROVED"), "ALREADY_DECIDED"),
        (
            lambda compiler: compiler.bundle.update(
                expires_at=_utc(NOW),
                source=dict(compiler.bundle["source"], expires_at=_utc(NOW)),
            ),
            "BUNDLE_EXPIRED",
        ),
        (
            lambda compiler: compiler.bundle["source"]["approval_policy"].update(
                approver_identity="other-owner"
            ),
            "OWNER_POLICY_MISMATCH",
        ),
        (
            lambda compiler: compiler.bundle["source"].update(
                independent_review={
                    **compiler.bundle["source"]["independent_review"],
                    "verdict": "REJECT",
                }
            ),
            "INDEPENDENT_REVIEW_INVALID",
        ),
        (lambda compiler: compiler.bundle.update(status="REVOKED"), "ALREADY_DECIDED"),
    ],
)
def test_ineligible_states_have_closed_reason(rail, mutator, reason) -> None:
    instance, compiler, _registry = rail
    mutator(compiler)
    dto = instance.inspect(BUNDLE_ID)
    assert dto["eligibility"] == {"eligible": False, "reason_code": reason}


def test_control_plane_self_modification_is_ineligible(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    compiler = FakeCompiler(
        _bundle(actions=[_action("self-modify", service=PROTECTED_SERVICE)]),
        registry,
    )
    caller_selected_incomplete = ActivationState(
        active=True,
        reason_code="ACTIVE",
        pin_set_sha256=PIN_SET_SHA256,
        registry_identity_sha256="a" * 64,
        protected_authority_ids=(),
        expires_at=_utc(NOW + timedelta(hours=1)),
    )
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: caller_selected_incomplete,
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    assert instance.inspect(BUNDLE_ID)["eligibility"] == {
        "eligible": False,
        "reason_code": "CONTROL_PLANE_SELF_MODIFICATION",
    }


def test_protected_identities_use_valid_action_authority_prefixes() -> None:
    prefixes = {value.partition(":")[0] for value in PROTECTED_AUTHORITY_IDS}
    assert {"svc", "dest", "env", "acct"} <= prefixes
    for prefix in ("svc", "dest", "env", "acct"):
        protected = next(
            value for value in PROTECTED_AUTHORITY_IDS if value.startswith(prefix + ":")
        )
        action = _action(
            f"protected-{prefix}",
            service=protected
            if prefix == "svc"
            else next(
                value
                for value in PROTECTED_AUTHORITY_IDS
                if value.startswith("svc:")
            ),
        )
        action_field = {
            "dest": "destination",
            "env": "environment",
            "acct": "account",
        }.get(prefix)
        if action_field is not None:
            action[action_field] = protected
        assert OwnerApprovalRail._self_modifies(
            {"actions": [action]},
            PROTECTED_AUTHORITY_IDS,
        )


def test_display_preserves_valid_multi_value_scope(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    bundle = _bundle()
    bundle["source"]["scope"] = {
        "environment": [
            "env:" + hashlib.sha256(b"personal").hexdigest(),
            "env:" + hashlib.sha256(b"staging").hexdigest(),
        ],
        "account": [
            "acct:" + hashlib.sha256(b"agentic").hexdigest(),
            "acct:" + hashlib.sha256(b"paper").hexdigest(),
        ],
        "destination": [
            "dest:" + hashlib.sha256(b"bounded").hexdigest(),
            "dest:" + hashlib.sha256(b"preview").hexdigest(),
        ],
    }
    compiler = FakeCompiler(bundle, registry)
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    assert instance.inspect(BUNDLE_ID)["scope"] == bundle["source"]["scope"]


@pytest.mark.parametrize(
    ("action_kind", "field"),
    [
        (kind, field)
        for kind in ("FINANCIAL", "DEPLOYMENT", "PUBLICATION", "MESSAGE")
        for field in DISPLAY_ACTION_FIELDS
        if field != "action_kind"
    ],
)
def test_every_compiler_action_kind_and_field_is_scanned_for_self_modification(
    action_kind: str,
    field: str,
) -> None:
    action: dict[str, object] = {"action_kind": action_kind}
    action[field] = {"nested": [PROTECTED_SERVICE]}
    assert OwnerApprovalRail._self_modifies(
        {"actions": [action]},
        PROTECTED_AUTHORITY_IDS,
    )


@pytest.mark.parametrize("protected_id", PROTECTED_AUTHORITY_IDS)
def test_every_fixed_authority_id_is_protected_at_any_action_depth(
    tmp_path: Path,
    protected_id: str,
) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    action = _action("nested-self-modification")
    action["parameters"].append(
        {
            "name": "nested",
            "value": {"targets": [{"authority": protected_id}]},
            "unit": "authority-id",
        }
    )
    compiler = FakeCompiler(_bundle(actions=[action]), registry)
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    assert instance.inspect(BUNDLE_ID)["eligibility"] == {
        "eligible": False,
        "reason_code": "CONTROL_PLANE_SELF_MODIFICATION",
    }


def test_read_only_bootstrap_never_issues_challenge(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    compiler = FakeCompiler(_bundle(), registry)
    inactive = ActivationState.inactive("READ_ONLY_BOOTSTRAP")
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: inactive,
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    assert instance.inspect(BUNDLE_ID)["eligibility"]["reason_code"] == (
        "READ_ONLY_BOOTSTRAP"
    )
    with pytest.raises(RailRefused, match="READ_ONLY_BOOTSTRAP"):
        instance.reauthenticate(BUNDLE_ID, OWNER)


def test_direct_receipt_provisioning_without_deciding_challenge_fails_closed(
    rail,
) -> None:
    instance, _compiler, registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    stored = instance._challenge(challenge.session_cookie)
    with pytest.raises(RailRefused, match="CHALLENGE_INVALID"):
        instance._provision_receipt(
            challenge=stored,
        )
    assert _compiler.provisioned_receipts == {}


def test_session_store_refuses_symlink_into_authority_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    before = registry.read_bytes()
    session_link = tmp_path / "sessions.sqlite3"
    session_link.symlink_to(registry)
    compiler = FakeCompiler(_bundle(), registry)
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=session_link,
        challenge_attestor=_challenge_mac,
    )
    with pytest.raises(RailRefused, match="SESSION_REGISTRY_INVALID"):
        instance.reauthenticate(BUNDLE_ID, OWNER)
    assert registry.read_bytes() == before


def test_new_reauthentication_invalidates_old_and_expires_within_sixty_seconds(
    rail,
) -> None:
    instance, _compiler, _registry = rail
    first = instance.reauthenticate(BUNDLE_ID, OWNER)
    second = instance.reauthenticate(BUNDLE_ID, OWNER)
    assert first.session_cookie != second.session_cookie
    assert first.csrf_challenge != second.csrf_challenge
    assert datetime.fromisoformat(second.expires_at) <= NOW + timedelta(seconds=60)
    with pytest.raises(RailRefused, match="CHALLENGE_SUPERSEDED"):
        instance.decide(
            BUNDLE_ID,
            owner=OWNER,
            session_cookie=first.session_cookie,
            csrf_challenge=first.csrf_challenge,
            decision="APPROVE",
            canonical_sha256=BUNDLE_SHA,
            expected_rev=1,
        )


def test_approve_once_is_challenge_bound_replay_safe_and_executes_nothing(rail) -> None:
    instance, compiler, registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    result = instance.decide(
        BUNDLE_ID,
        owner=OWNER,
        session_cookie=challenge.session_cookie,
        csrf_challenge=challenge.csrf_challenge,
        decision="APPROVE",
        canonical_sha256=BUNDLE_SHA,
        expected_rev=1,
    )
    assert result["status"] == "APPROVED"
    assert result["message"] == (
        "Approval recorded. Nothing executed. Consumer remains disarmed."
    )
    replay = instance.decide(
        BUNDLE_ID,
        owner=OWNER,
        session_cookie=challenge.session_cookie,
        csrf_challenge=challenge.csrf_challenge,
        decision="APPROVE",
        canonical_sha256=BUNDLE_SHA,
        expected_rev=1,
    )
    assert replay == result
    assert len(compiler.approve_calls) == 1
    assert len(compiler.provisioned_receipts) == 1
    assert len(compiler.consumed_receipts) == 1


def test_decision_rechecks_all_live_eligibility_before_claiming_challenge(rail) -> None:
    instance, compiler, _registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    compiler.bundle["source"]["approval_policy"]["approver_identity"] = "other"
    with pytest.raises(RailRefused, match="BUNDLE_CHANGED"):
        instance.decide(
            BUNDLE_ID,
            owner=OWNER,
            session_cookie=challenge.session_cookie,
            csrf_challenge=challenge.csrf_challenge,
            decision="APPROVE",
            canonical_sha256=BUNDLE_SHA,
            expected_rev=1,
        )
    assert compiler.approve_calls == []


@pytest.mark.parametrize("failpoint", ["before", "after"])
def test_approval_recovers_idempotently_across_lifecycle_crash(
    tmp_path: Path,
    failpoint: str,
) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    compiler = FakeCompiler(
        _bundle(),
        registry,
        approve_fail_once=failpoint,
    )
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=os.urandom,
        session_registry_path=tmp_path / "sessions.sqlite3",
        challenge_attestor=_challenge_mac,
    )
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    arguments = {
        "owner": OWNER,
        "session_cookie": challenge.session_cookie,
        "csrf_challenge": challenge.csrf_challenge,
        "decision": "APPROVE",
        "canonical_sha256": BUNDLE_SHA,
        "expected_rev": 1,
    }
    with pytest.raises(RuntimeError, match="simulated crash"):
        instance.decide(BUNDLE_ID, **arguments)
    recovered = instance.decide(BUNDLE_ID, **arguments)
    assert recovered["status"] == "APPROVED"
    assert len(compiler.approve_calls) == 1
    assert len(compiler.provisioned_receipts) == 1
    assert len(compiler.consumed_receipts) == 1


def test_concurrent_same_challenge_has_one_authority_and_stable_result(rail) -> None:
    instance, compiler, _registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    barrier = threading.Barrier(2)
    results: list[dict] = []
    failures: list[Exception] = []

    def decide() -> None:
        barrier.wait()
        try:
            results.append(
                instance.decide(
                    BUNDLE_ID,
                    owner=OWNER,
                    session_cookie=challenge.session_cookie,
                    csrf_challenge=challenge.csrf_challenge,
                    decision="APPROVE",
                    canonical_sha256=BUNDLE_SHA,
                    expected_rev=1,
                )
            )
        except Exception as error:  # pragma: no cover - asserted below
            failures.append(error)

    workers = [threading.Thread(target=decide) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert failures == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert len(compiler.approve_calls) == 1


def test_refusal_is_exact_terminal_and_never_provisions_attended_receipt(rail) -> None:
    instance, compiler, registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    result = instance.decide(
        BUNDLE_ID,
        owner=OWNER,
        session_cookie=challenge.session_cookie,
        csrf_challenge=challenge.csrf_challenge,
        decision="REFUSE",
        canonical_sha256=BUNDLE_SHA,
        expected_rev=1,
    )
    assert result["status"] == "REVOKED"
    assert result["message"] == (
        "Refusal recorded. Nothing executed. Consumer remains disarmed."
    )
    assert compiler.revoke_calls[0]["reason"] == "OWNER_REFUSED"
    assert compiler.provisioned_receipts == {}


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("owner", "other", "OWNER_MISMATCH"),
        ("session_cookie", "wrong", "SESSION_INVALID"),
        ("csrf_challenge", "wrong", "CSRF_INVALID"),
        ("canonical_sha256", "f" * 64, "BUNDLE_CHANGED"),
        ("expected_rev", 2, "BUNDLE_CHANGED"),
    ],
)
def test_decision_binding_mismatch_fails_before_lifecycle_call(
    rail, field, value, code
) -> None:
    instance, compiler, _registry = rail
    challenge = instance.reauthenticate(BUNDLE_ID, OWNER)
    arguments = {
        "owner": OWNER,
        "session_cookie": challenge.session_cookie,
        "csrf_challenge": challenge.csrf_challenge,
        "decision": "APPROVE",
        "canonical_sha256": BUNDLE_SHA,
        "expected_rev": 1,
    }
    arguments[field] = value
    with pytest.raises(RailRefused, match=code):
        instance.decide(BUNDLE_ID, **arguments)
    assert compiler.approve_calls == []


def _app_for(instance: OwnerApprovalRail, asset_dir: Path) -> FastAPI:
    app = FastAPI()

    def authenticate(username: str, password: str) -> str:
        if hmac.compare_digest(username, OWNER) and hmac.compare_digest(
            password, PASSWORD
        ):
            return OWNER
        raise RailRefused("AUTH_INVALID", 401)

    app.include_router(
        create_owner_approval_router(
            instance,
            authenticate=authenticate,
            asset_dir=asset_dir,
            containerized=lambda: False,
        )
    )
    return app


def test_api_is_owner_only_private_no_store_and_exact_shape(
    rail, tmp_path: Path, monkeypatch
) -> None:
    instance, compiler, _registry = rail
    (tmp_path / "approval.html").write_text("<main>owner rail</main>")
    client = TestClient(
        _app_for(instance, tmp_path),
        base_url="https://127.0.0.1:8099",
        client=("127.0.0.1", 50000),
    )
    path = f"/api/operator/v1/approval-bundles/{BUNDLE_ID}"
    assert client.get(path).status_code == 401
    response = client.get(path, auth=(OWNER, PASSWORD))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["pragma"] == "no-cache"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.json()["canonical_sha256"] == BUNDLE_SHA
    assert (
        client.get(
            f"/operator/approvals/{BUNDLE_ID}", auth=(OWNER, PASSWORD)
        ).status_code
        == 200
    )

    compiler.bundle["source"]["approval_policy"]["approver_identity"] = "other"
    assert client.get(path, auth=(OWNER, PASSWORD)).status_code == 403


def test_api_cloud_and_remote_hard_404_before_auth(
    rail, tmp_path: Path, monkeypatch
) -> None:
    instance, _compiler, _registry = rail
    app = _app_for(instance, tmp_path)
    remote = TestClient(
        app,
        base_url="https://127.0.0.1:8099",
        client=("203.0.113.9", 50000),
    )
    path = f"/api/operator/v1/approval-bundles/{BUNDLE_ID}"
    assert remote.get(path).status_code == 404
    monkeypatch.setenv("K_SERVICE", "public-service")
    local = TestClient(
        app,
        base_url="https://127.0.0.1:8099",
        client=("127.0.0.1", 50000),
    )
    assert local.get(path, auth=(OWNER, PASSWORD)).status_code == 404


def test_api_mutations_require_https_origin_host_json_and_same_origin_fetch(
    rail, tmp_path: Path
) -> None:
    instance, compiler, _registry = rail
    client = TestClient(
        _app_for(instance, tmp_path),
        base_url="https://127.0.0.1:8099",
        client=("127.0.0.1", 50000),
    )
    path = f"/api/operator/v1/approval-bundles/{BUNDLE_ID}/reauth"
    good = {
        "Origin": "https://127.0.0.1:8099",
        "Content-Type": "application/json",
        "Sec-Fetch-Site": "same-origin",
    }
    assert client.post(path, auth=(OWNER, PASSWORD)).status_code == 415
    assert (
        client.post(
            path,
            auth=(OWNER, PASSWORD),
            headers=dict(good, Origin="https://evil.invalid"),
            json={},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path,
            auth=(OWNER, PASSWORD),
            headers=dict(good, **{"Sec-Fetch-Site": "cross-site"}),
            json={},
        ).status_code
        == 403
    )
    issued = client.post(path, auth=(OWNER, PASSWORD), headers=good, json={})
    assert issued.status_code == 200
    challenge = issued.json()
    cookie = issued.cookies.get("sapphire_owner_session")
    decision = client.post(
        f"/api/operator/v1/approval-bundles/{BUNDLE_ID}/decision",
        auth=(OWNER, PASSWORD),
        headers=good,
        cookies={"sapphire_owner_session": cookie},
        json={
            "decision": "APPROVE",
            "canonical_sha256": BUNDLE_SHA,
            "expected_rev": 1,
            "csrf_challenge": challenge["csrf_challenge"],
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "APPROVED"
    assert len(compiler.approve_calls) == 1


def test_api_rejects_client_authored_fields_and_freeform_refusal(
    rail, tmp_path: Path
) -> None:
    instance, compiler, _registry = rail
    client = TestClient(
        _app_for(instance, tmp_path),
        base_url="https://127.0.0.1:8099",
        client=("127.0.0.1", 50000),
    )
    headers = {
        "Origin": "https://127.0.0.1:8099",
        "Content-Type": "application/json",
        "Sec-Fetch-Site": "same-origin",
    }
    issued = client.post(
        f"/api/operator/v1/approval-bundles/{BUNDLE_ID}/reauth",
        auth=(OWNER, PASSWORD),
        headers=headers,
        json={},
    )
    body = {
        "decision": "REFUSE",
        "canonical_sha256": BUNDLE_SHA,
        "expected_rev": 1,
        "csrf_challenge": issued.json()["csrf_challenge"],
        "reason": "browser-authored text",
    }
    response = client.post(
        f"/api/operator/v1/approval-bundles/{BUNDLE_ID}/decision",
        auth=(OWNER, PASSWORD),
        headers=headers,
        cookies={
            "sapphire_owner_session": issued.cookies.get("sapphire_owner_session")
        },
        json=body,
    )
    assert response.status_code == 422
    assert compiler.revoke_calls == []


def test_module_has_no_consumer_connector_network_process_or_secret_logging() -> None:
    path = Path(__file__).resolve().parents[1] / "owner_approval.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not (
        {
            "httpx",
            "requests",
            "urllib",
            "socket",
            "subprocess",
            "fund",
            "approval_consumer",
        }
        & imports
    )
    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "ApprovalConsumer",
        "precheck(",
        "invoke(",
        "observe_outcome(",
        "importlib",
        "approval_connection",
        "attended_approval_receipts",
        "gcloud",
        "robinhood",
        "wallet",
        "private_key",
        "logger.",
        "log.",
    ):
        assert forbidden not in source
    assert "\n    def _connect(" not in source
    assert "._connect(" not in source

    frontend = (
        path.parents[1] / "frontend" / "src" / "operator-approval" / "ApprovalApp.tsx"
    ).read_text(encoding="utf-8")
    for persistent_authority in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "serviceWorker",
    ):
        assert persistent_authority not in frontend
    assert "canonical_sha256: bundle.canonical_sha256" in frontend
    assert "expected_rev: bundle.rev" in frontend
    assert "csrf_challenge: challenge.csrf_challenge" in frontend


def test_exact_held_fleet_source_executes_without_ambient_import(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "registry.sqlite3"
    _initialize_registry(registry)
    core_path = tmp_path / "core.py"
    core_source = b'HELD_CORE = "exact-core-bytes"\n'
    core_path.write_bytes(core_source)
    approvals_path = tmp_path / "approvals.py"
    approvals_source = (
        b"from .core import HELD_CORE\n"
        b'BUNDLE_SCHEMA_VERSION = "held-test/v1"\n'
        b"class ApprovalBundleDB:\n"
        b"    def __init__(self, path):\n"
        b"        self.path = path\n"
        b"        self.core_identity = HELD_CORE\n"
    )
    approvals_path.write_bytes(approvals_source)
    database = FleetLeaseCompilerPort._load_held_database(
        registry_path=registry,
        core_path=core_path,
        approvals_path=approvals_path,
        core_size=len(core_source),
        core_sha256=hashlib.sha256(core_source).hexdigest(),
        approvals_size=len(approvals_source),
        approvals_sha256=hashlib.sha256(approvals_source).hexdigest(),
        schema_version="held-test/v1",
    )
    assert database.__class__.__module__.startswith("_sapphire_held_fleet_")
    assert database.path == registry
    assert database.core_identity == "exact-core-bytes"
    adapter_source = (
        Path(__file__).resolve().parents[1] / "owner_approval.py"
    ).read_text(encoding="utf-8")
    assert "_attended_challenge_verifier" not in adapter_source
    assert "challenge_verifier" not in adapter_source


def test_public_app_excludes_owner_approval_and_local_runtime_is_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    public_source = (backend / "main.py").read_text(encoding="utf-8")
    local_source = (backend / "local_owner_main.py").read_text(encoding="utf-8")
    launcher = (backend.parent / "scripts" / "run_owner_approval_local.py").read_text(
        encoding="utf-8"
    )
    assert "owner_approval" not in public_source
    assert 'OWNER = "ari"' in launcher
    assert 'HOST = "127.0.0.1"' in launcher
    assert 'PORT = "8099"' in launcher
    assert "backend.local_owner_main:app" in launcher
    assert '"--host",\n        HOST' in launcher
    assert "create_owner_approval_router" in local_source
    assert "configured_owner != OWNER" in local_source
    assert "docs_url=None" in local_source
    import local_owner_main

    monkeypatch.setenv("AUTH_USERNAME", OWNER)
    monkeypatch.setenv("AUTH_PASSWORD", PASSWORD)
    assert local_owner_main.authenticate_owner(OWNER, PASSWORD) == OWNER
    with pytest.raises(RailRefused, match="AUTH_INVALID"):
        local_owner_main.authenticate_owner("sapphire", PASSWORD)


def test_frontend_render_contract_exactly_matches_closed_backend_fields() -> None:
    frontend = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "operator-approval"
        / "ApprovalApp.tsx"
    ).read_text(encoding="utf-8")

    def rendered_fields(name: str) -> tuple[str, ...]:
        marker = f"export const {name} = ["
        start = frontend.index(marker) + len(marker)
        end = frontend.index("] as const", start)
        return tuple(
            node.value
            for node in ast.parse("[" + frontend[start:end] + "]").body[0].value.elts
            if isinstance(node, ast.Constant) and type(node.value) is str
        )

    assert rendered_fields("RENDERED_ACTION_FIELDS") == DISPLAY_ACTION_FIELDS
    assert rendered_fields("RENDERED_FINANCIAL_FIELDS") == DISPLAY_FINANCIAL_FIELDS
    assert rendered_fields("RENDERED_REVIEW_FIELDS") == DISPLAY_REVIEW_FIELDS
    for field in DISPLAY_ACTION_FIELDS:
        assert f"action.{field}" in frontend
    for field in DISPLAY_FINANCIAL_FIELDS:
        assert f"action.financial.{field}" in frontend
    for field in DISPLAY_REVIEW_FIELDS:
        assert f"bundle.independent_review.{field}" in frontend


def test_combined_image_copies_the_isolated_approval_entrypoint() -> None:
    dockerfile = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert any(
        line.startswith("COPY frontend/") and "frontend/approval.html" in line
        for line in dockerfile.splitlines()
    )

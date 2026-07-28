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
    PIN_SET_SHA256,
    ActivationState,
    ActivationVerifier,
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
PROTECTED_SERVICE = "svc:" + hashlib.sha256(b"approval-rail").hexdigest()


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


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

    def approval_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.registry, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

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
            assert kwargs["approval_statement"] == self.bundle["source"]["approval_statement"]
            assert kwargs["actor"] == OWNER
            with self.approval_connection() as connection:
                receipt = connection.execute(
                    "SELECT * FROM attended_approval_receipts WHERE receipt_sha256 = ?",
                    (kwargs["attended_receipt_sha256"],),
                ).fetchone()
                assert receipt is not None
                assert receipt["consumed_at"] is None
                connection.execute(
                    "UPDATE attended_approval_receipts SET consumed_at = ? "
                    "WHERE receipt_sha256 = ?",
                    (_utc(NOW), kwargs["attended_receipt_sha256"]),
                )
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
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE attended_approval_receipts (
                receipt_sha256 TEXT PRIMARY KEY,
                bundle_sha256 TEXT NOT NULL,
                statement_sha256 TEXT NOT NULL,
                approver_identity TEXT NOT NULL,
                approver_class TEXT NOT NULL,
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            );
            """
        )
    path.chmod(0o600)


def _active() -> ActivationState:
    return ActivationState(
        active=True,
        reason_code="ACTIVE",
        pin_set_sha256=PIN_SET_SHA256,
        registry_identity_sha256="a" * 64,
        protected_authority_ids=(PROTECTED_SERVICE,),
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
    )
    return instance, compiler, registry


def test_local_context_rejects_cloud_container_wildcard_and_remote() -> None:
    assert (
        local_context_reason("127.0.0.1", "127.0.0.1:8099", {}, False)
        is None
    )
    assert local_context_reason("203.0.113.4", "127.0.0.1:8099", {}, False) == (
        "NON_LOOPBACK_PEER"
    )
    assert local_context_reason("127.0.0.1", "0.0.0.0:8099", {}, False) == (
        "NON_LOOPBACK_HOST"
    )
    assert local_context_reason("127.0.0.1", "localhost:8099", {}, False) == (
        "NON_LOOPBACK_HOST"
    )
    assert local_context_reason("127.0.0.1", "127.0.0.1:8099", {"K_SERVICE": "x"}, False) == (
        "CLOUD_RUNTIME"
    )
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
        "protected_authority_ids": [PROTECTED_SERVICE],
    }
    payload["mac_sha256"] = hmac.new(
        key.read_bytes(),
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    attestation.write_text(canonical_json(payload), encoding="utf-8")
    attestation.chmod(0o600)
    verifier = ActivationVerifier(
        registry_path=registry,
        attestation_path=attestation,
        key_path=key,
    )
    state = verifier.verify(NOW)
    assert state.active is True
    assert state.protected_authority_ids == (PROTECTED_SERVICE,)

    substituted_registry = tmp_path / "substituted.sqlite3"
    substituted_registry.write_bytes(registry.read_bytes())
    substituted_registry.chmod(0o600)
    substituted = ActivationVerifier(
        registry_path=substituted_registry,
        attestation_path=attestation,
        key_path=key,
    )
    assert substituted.verify(NOW).reason_code == "ACTIVATION_BINDING_INVALID"

    payload["mac_sha256"] = "f" * 64
    attestation.write_text(canonical_json(payload), encoding="utf-8")
    assert verifier.verify(NOW).reason_code == "ACTIVATION_MAC_INVALID"
    attestation.chmod(0o644)
    assert verifier.verify(NOW).reason_code == "ACTIVATION_FILE_INVALID"


def test_inspection_is_exact_ordered_and_read_only(rail) -> None:
    instance, compiler, registry = rail
    before = registry.read_bytes()
    dto = instance.inspect(BUNDLE_ID)
    assert dto["canonical_sha256"] == BUNDLE_SHA
    assert len(dto["canonical_sha256"]) == 64
    assert dto["rev"] == 1
    assert dto["compile_receipt_sha256"] == hashlib.sha256(
        b"compile-receipt"
    ).hexdigest()
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
    instance = OwnerApprovalRail(
        compiler=compiler,
        activation=lambda _now: _active(),
        clock=lambda: NOW,
        token_bytes=os.urandom,
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
            statement=_bundle()["source"]["approval_statement"],
        )
    with sqlite3.connect(registry) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM attended_approval_receipts"
        ).fetchone()[0] == 0


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
    with sqlite3.connect(registry) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM attended_approval_receipts"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM owner_approval_rail_receipts"
        ).fetchone()[0] == 1


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
    with sqlite3.connect(registry) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM owner_approval_rail_receipts"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM attended_approval_receipts"
        ).fetchone()[0] == 1


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
    with sqlite3.connect(registry) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM attended_approval_receipts"
        ).fetchone()[0] == 0


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
    assert client.get(
        f"/operator/approvals/{BUNDLE_ID}", auth=(OWNER, PASSWORD)
    ).status_code == 200

    compiler.bundle["source"]["approval_policy"]["approver_identity"] = "other"
    assert client.get(path, auth=(OWNER, PASSWORD)).status_code == 403


def test_api_cloud_and_remote_hard_404_before_auth(rail, tmp_path: Path, monkeypatch) -> None:
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
    assert client.post(
        path,
        auth=(OWNER, PASSWORD),
        headers=dict(good, Origin="https://evil.invalid"),
        json={},
    ).status_code == 403
    assert client.post(
        path,
        auth=(OWNER, PASSWORD),
        headers=dict(good, **{"Sec-Fetch-Site": "cross-site"}),
        json={},
    ).status_code == 403
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


def test_api_rejects_client_authored_fields_and_freeform_refusal(rail, tmp_path: Path) -> None:
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
        cookies={"sapphire_owner_session": issued.cookies.get("sapphire_owner_session")},
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
        "gcloud",
        "robinhood",
        "wallet",
        "private_key",
        "logger.",
        "log.",
    ):
        assert forbidden not in source

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


def test_combined_image_copies_the_isolated_approval_entrypoint() -> None:
    dockerfile = (
        Path(__file__).resolve().parents[2] / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert any(
        line.startswith("COPY frontend/") and "frontend/approval.html" in line
        for line in dockerfile.splitlines()
    )

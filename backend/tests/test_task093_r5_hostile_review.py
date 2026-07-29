"""Task 093 R5 goldens for both sealed R4 hostile reviews.

Every file probe is confined to ``tmp_path`` and every telemetry probe is
in-memory. Nothing here reaches a provider, service, credential, message
transport, broker, wallet, order, trade, or pause file.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import main
from live_telemetry import LiveTelemetryStore, validate_snapshot
from tests.test_live_telemetry import _sample


NOW = datetime.now(UTC) - timedelta(seconds=5)
OLD = NOW - timedelta(days=3)


class _FixedPersistence:
    def __init__(self, snapshot: Any, *, received_at: float | None = None):
        self.snapshot = snapshot
        self.received_at = NOW.timestamp() if received_at is None else received_at

    def accept(
        self,
        snapshot: dict[str, Any],
        *,
        nonce: str,
        received_at: float,
    ) -> None:
        raise AssertionError("read-only hostile persistence")

    def select(self, *, received_before: float) -> tuple[float, Any]:
        return self.received_at, self.snapshot

    def has_history(self) -> bool:
        return True

    def reset(self) -> None:
        raise AssertionError("read-only hostile persistence")


def _clear_pause_files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for source in ("mac", "rh_chain"):
        path = root / f"{source}-pause.json"
        path.write_text(
            json.dumps({"state": "clear", "observed_at": NOW.isoformat()}),
            encoding="utf-8",
        )
        path.chmod(0o600)
        result[source] = path
    return result


def _set_runtime_root(
    monkeypatch: pytest.MonkeyPatch,
    rh_chain: Path,
    pause_root: Path,
) -> None:
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_chain)
    monkeypatch.setattr(main, "_PAUSE_SENTINELS", _clear_pause_files(pause_root))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


def _fresh_gate() -> dict[str, Any]:
    return {
        "observed_at": NOW.isoformat(),
        "armed": True,
        "mode": "bounded_auto",
        "cap_usd": 999,
    }


def _read_gate_in_child(
    rh_chain: str,
    pause_files: dict[str, str],
    now: str,
    output: Any,
) -> None:
    """Isolate a hostile FIFO so a red golden cannot hang the pytest worker."""
    main._RH_CHAIN_DIR = Path(rh_chain)
    main._PAUSE_SENTINELS = {
        source: Path(path) for source, path in pause_files.items()
    }
    output.put(main._gate_status(now=datetime.fromisoformat(now))["state"])


def _assert_gate_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    rh_chain: Path,
    pause_root: Path,
) -> None:
    _set_runtime_root(monkeypatch, rh_chain, pause_root)
    gate = main._gate_status(now=NOW)
    assert gate["state"] == "unavailable"
    assert gate["armed"] is None
    assert gate["mode"] == "unavailable"


def test_public_ingest_rejects_recursive_json_as_client_error() -> None:
    client = TestClient(main.app, raise_server_exceptions=False)
    nested = ("[" * 2_000) + "0" + ("]" * 2_000)

    response = client.post(
        "/api/v1/telemetry",
        content=nested.encode(),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid telemetry JSON"}


def test_public_ingest_rejects_duplicate_json_keys_before_auth() -> None:
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/telemetry",
        content=b'{"version":1,"version":1}',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid telemetry JSON"}


def test_malformed_durable_snapshot_fails_closed_instead_of_raising() -> None:
    store = LiveTelemetryStore(
        _FixedPersistence(
            {
                "observed_at": "not-a-timestamp",
                "summary": {"active_agents": 99},
                "agents": ["malformed"],
            }
        )
    )

    projected = store.get(now=NOW.timestamp())

    assert projected["status"] == "offline"
    assert projected["observed_at"] is None
    assert projected["summary"]["active_agents"] is None
    assert projected["agents"] == []


def test_recursive_nonfinite_and_incomplete_durable_snapshots_fail_closed() -> None:
    malformed = [
        {"observed_at": NOW.isoformat(), "nested": [[[[[float("nan")]]]]]},
        {"version": 1, "observed_at": NOW.isoformat()},
        ["not", "an", "object"],
    ]

    for raw in malformed:
        projected = LiveTelemetryStore(_FixedPersistence(raw)).get(
            now=NOW.timestamp()
        )
        assert projected["status"] == "offline"
        assert projected["observed_at"] is None
        assert projected["agents"] == []


def test_nested_evidence_after_parent_observation_never_resurrects() -> None:
    read_time = datetime.now(UTC) - timedelta(minutes=2)
    parent_time = read_time - timedelta(seconds=60)
    nested_time = read_time - timedelta(seconds=30)
    raw = _sample(observed_at=parent_time.isoformat(), sequence=9501)
    raw["summary"]["active_agents"] = 1
    raw["agents"][0]["updated_at"] = nested_time.isoformat()
    raw["desk"]["updated_at"] = nested_time.isoformat()
    raw["events"][0]["observed_at"] = nested_time.isoformat()
    stored = validate_snapshot(raw)
    store = LiveTelemetryStore(_FixedPersistence(stored))

    projected = store.get(now=read_time.timestamp(), stale_after_seconds=180)

    assert projected["status"] == "live"
    assert projected["agents"][0]["state"] == "offline"
    assert projected["summary"]["active_agents"] is None
    assert projected["desk"]["posture"] == "unknown"
    assert projected["events"] == []


def test_stale_nested_event_is_withdrawn_from_current_parent() -> None:
    raw = _sample(observed_at=NOW.isoformat(), sequence=9503)
    raw["events"][0]["observed_at"] = OLD.isoformat()
    stored = validate_snapshot(raw)
    projected = LiveTelemetryStore(_FixedPersistence(stored)).get(
        now=NOW.timestamp(),
        stale_after_seconds=180,
    )

    assert projected["status"] == "live"
    assert projected["events"] == []


def test_duplicate_agent_and_event_ids_cannot_inflate_current_evidence() -> None:
    raw = _sample(observed_at=NOW.isoformat(), sequence=9502)
    raw["agents"].append({**raw["agents"][0]})
    raw["events"].append({**raw["events"][0]})
    raw["summary"]["active_agents"] = 2

    with pytest.raises(ValueError):
        validate_snapshot(raw)


@pytest.mark.parametrize(
    ("primary", "aliases"),
    [
        ("malformed", {"updated_at": NOW.isoformat()}),
        (NOW.isoformat(), {"updated_at": NOW.isoformat()}),
        (NOW.isoformat(), {"timestamp": (NOW - timedelta(seconds=1)).isoformat()}),
        (None, {"updated_at": NOW.isoformat()}),
        ((NOW + timedelta(seconds=30)).isoformat(), {}),
        (OLD.isoformat(), {}),
    ],
)
def test_gate_has_one_strict_current_observed_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    primary: str | None,
    aliases: dict[str, str],
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    document = {**_fresh_gate(), **aliases}
    if primary is None:
        document.pop("observed_at")
    else:
        document["observed_at"] = primary
    _write_json(rh_chain / "gate.json", document)

    _assert_gate_unavailable(monkeypatch, rh_chain, tmp_path)


def test_duplicate_gate_keys_are_rejected_instead_of_last_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    path = rh_chain / "gate.json"
    path.write_text(
        (
            '{"observed_at":'
            + json.dumps(NOW.isoformat())
            + ',"armed":false,"armed":true,"mode":"bounded_auto"}'
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)

    _assert_gate_unavailable(monkeypatch, rh_chain, tmp_path)


@pytest.mark.parametrize(
    "attack",
    [
        "symlink",
        "hardlink",
        "directory",
        "group_writable",
        "oversize",
        "deep",
    ],
)
def test_gate_runtime_document_requires_stable_bounded_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    path = rh_chain / "gate.json"
    target = tmp_path / "attacker-gate.json"
    _write_json(target, _fresh_gate())

    if attack == "symlink":
        os.symlink(target, path)
    elif attack == "hardlink":
        os.link(target, path)
    elif attack == "directory":
        path.mkdir()
    elif attack == "group_writable":
        _write_json(path, _fresh_gate())
        path.chmod(0o620)
    elif attack == "oversize":
        value = {**_fresh_gate(), "padding": "x" * (128 * 1024)}
        _write_json(path, value)
    elif attack == "deep":
        path.write_text(
            '{"observed_at":'
            + json.dumps(NOW.isoformat())
            + ',"armed":true,"mode":"bounded_auto","nested":'
            + ("[" * 80)
            + "0"
            + ("]" * 80)
            + "}",
            encoding="utf-8",
        )
        path.chmod(0o600)

    _assert_gate_unavailable(monkeypatch, rh_chain, tmp_path)


def test_fifo_gate_fails_closed_without_blocking(tmp_path: Path) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    os.mkfifo(rh_chain / "gate.json")
    pause_files = _clear_pause_files(tmp_path)
    context = multiprocessing.get_context("fork")
    output = context.Queue()
    process = context.Process(
        target=_read_gate_in_child,
        args=(
            str(rh_chain),
            {source: str(path) for source, path in pause_files.items()},
            NOW.isoformat(),
            output,
        ),
    )
    process.start()
    process.join(timeout=1.0)
    blocked = process.is_alive()
    if blocked:
        process.terminate()
        process.join(timeout=1.0)

    assert not blocked, "runtime reader blocked on a FIFO"
    assert output.get(timeout=1.0) == "unavailable"


def test_symlinked_executor_heartbeat_is_not_admitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    target = tmp_path / "attacker-heartbeat.json"
    _write_json(
        target,
        {
            "observed_at": NOW.isoformat(),
            "status": "alive",
            "alive": True,
            "pid": 4242,
        },
    )
    os.symlink(target, rh_chain / "executor-heartbeat.json")
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_chain)

    assert main._executor_heartbeat(now=NOW) == {
        "status": "unknown",
        "alive": None,
        "last_seen": None,
        "pid": None,
    }


@pytest.mark.parametrize(
    ("document", "last_seen"),
    [
        ({"updated_at": NOW.isoformat(), "status": "alive", "pid": 1}, None),
        (
            {
                "observed_at": "malformed",
                "updated_at": NOW.isoformat(),
                "status": "alive",
                "pid": 1,
            },
            None,
        ),
        (
            {
                "observed_at": OLD.isoformat(),
                "status": "alive",
                "alive": True,
                "pid": 1,
            },
            OLD.isoformat(),
        ),
    ],
)
def test_heartbeat_requires_one_strict_current_observed_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: dict[str, Any],
    last_seen: str | None,
) -> None:
    _write_json(tmp_path / "executor-heartbeat.json", document)
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path)

    assert main._executor_heartbeat(now=NOW) == {
        "status": "unknown",
        "alive": None,
        "last_seen": last_seen,
        "pid": None,
    }


def test_stale_skin_book_withdraws_every_substantive_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    _write_json(
        rh_chain / "skin-book.json",
        {
            "observed_at": OLD.isoformat(),
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
            "mode": "bounded_auto",
            "deployed_usd": 999,
            "n_open": 9,
            "positions": [{"symbol": "BTC"}] * 3,
            "fills": [{"symbol": "ETH"}] * 4,
            "skin_in_game": True,
            "limits": {"per_order_cap_pct": 95},
        },
    )
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_chain)

    skin = main._skin_book(now=NOW)
    wallet = main._wallet_status(now=NOW)
    assert {
        "mode": skin["mode"],
        "deployed_usd": skin["deployed_usd"],
        "n_open": skin["n_open"],
        "positions_count": skin["positions_count"],
        "fills_count": skin["fills_count"],
        "skin_in_game": skin["skin_in_game"],
        "limits": skin["limits"],
        "address": wallet["address"],
    } == {
        "mode": "unavailable",
        "deployed_usd": None,
        "n_open": None,
        "positions_count": None,
        "fills_count": None,
        "skin_in_game": None,
        "limits": {},
        "address": None,
    }
    assert skin["updated_at"] == OLD.isoformat()


def test_symlinked_skin_book_and_alias_time_are_not_admitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rh_chain = tmp_path / "rh-chain"
    rh_chain.mkdir()
    target = tmp_path / "attacker-skin.json"
    _write_json(
        target,
        {
            "updated_at": NOW.isoformat(),
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
            "deployed_usd": 888,
            "n_open": 8,
            "skin_in_game": True,
            "limits": {"daily": 777},
        },
    )
    os.symlink(target, rh_chain / "skin-book.json")
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", rh_chain)

    wallet = main._wallet_status(now=NOW)
    assert wallet["address"] is None
    assert wallet["deployed_usd"] is None
    assert wallet["n_open"] is None
    assert wallet["skin_in_game"] is None
    assert wallet["limits"] == {}


def test_stale_signal_is_not_returned_to_public_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_json(
        tmp_path / "signals.json",
        [
            {
                "instrument": "BTC",
                "side": "BUY",
                "venue": "attacker",
                "confidence": "high",
                "timestamp": OLD.isoformat(),
            }
        ],
    )
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path)

    assert main._public_signals(main._recent_signals(now=NOW)) == []


def test_signals_reject_symlink_duplicate_key_and_alias_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_RH_CHAIN_DIR", tmp_path)
    target = tmp_path / "target.json"
    _write_json(
        target,
        [
            {
                "instrument": "BTC",
                "side": "BUY",
                "updated_at": NOW.isoformat(),
            }
        ],
    )
    os.symlink(target, tmp_path / "signals.json")
    assert main._recent_signals(now=NOW) == []

    (tmp_path / "signals.json").unlink()
    path = tmp_path / "signals.json"
    path.write_text(
        (
            '[{"instrument":"BTC","side":"BUY","timestamp":'
            + json.dumps(NOW.isoformat())
            + ',"side":"SELL"}]'
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    assert main._recent_signals(now=NOW) == []


def test_fleet_rejects_symlinked_duplicate_and_stale_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(main.app)
    target = tmp_path / "fleet-target.json"
    _write_json(
        target,
        {
            "generated_at": NOW.isoformat(),
            "leases": [{"agent": "spoof"}],
            "gates": [],
        },
    )
    path = tmp_path / "fleet.json"
    os.symlink(target, path)
    monkeypatch.setenv("FLEET_SNAPSHOT_PATH", str(path))
    assert client.get("/api/fleet").json()["leases"] is None

    path.unlink()
    path.write_text(
        (
            '{"generated_at":'
            + json.dumps(NOW.isoformat())
            + ',"leases":[],"leases":[{"agent":"spoof"}],"gates":[]}'
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    assert client.get("/api/fleet").json()["leases"] is None

    _write_json(
        path,
        {"generated_at": OLD.isoformat(), "leases": [{"agent": "spoof"}], "gates": []},
    )
    assert client.get("/api/fleet").json()["leases"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {
            "total": 1,
            "alerts": [
                {"observed_at": "malformed", "updated_at": NOW.isoformat()}
            ],
        },
        {"total": 1, "alerts": [{"observed_at": OLD.isoformat()}]},
        {
            "total": 1,
            "alerts": [
                {"observed_at": (NOW + timedelta(minutes=5)).isoformat()}
            ],
        },
    ],
)
def test_tradingview_last_ping_requires_one_strict_current_observed_at(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
) -> None:
    class Response:
        status_code = 200
        content = json.dumps(payload).encode()

        @staticmethod
        def json() -> dict[str, Any]:
            return payload

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str) -> Response:
            return Response()

    async def healthy(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return {"name": "tradingview_webhook", "status": "ok", "http_status": 200}

    monkeypatch.setattr(
        main,
        "_env",
        lambda key, default="": (
            "https://example.invalid" if key == "TV_WEBHOOK_URL" else default
        ),
    )
    monkeypatch.setattr(main, "_probe_health", healthy)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **_kwargs: Client())
    monkeypatch.setattr(main, "_tv_probe_cache", {"ts": 0.0, "result": None})

    projected = asyncio.run(main._probe_tradingview_webhook())
    assert projected["last_ping"] is None
    assert projected["pending_alerts"] == 0


def test_tradingview_duplicate_json_keys_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = (
            b'{"total":1,"alerts":[{"observed_at":"'
            + NOW.isoformat().encode()
            + b'","observed_at":"'
            + NOW.isoformat().encode()
            + b'"}]}'
        )

        @staticmethod
        def json() -> dict[str, Any]:
            return {
                "total": 1,
                "alerts": [{"observed_at": NOW.isoformat()}],
            }

    class Client:
        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, _url: str) -> Response:
            return Response()

    async def healthy(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return {"name": "tradingview_webhook", "status": "ok", "http_status": 200}

    monkeypatch.setattr(
        main,
        "_env",
        lambda key, default="": (
            "https://example.invalid" if key == "TV_WEBHOOK_URL" else default
        ),
    )
    monkeypatch.setattr(main, "_probe_health", healthy)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **_kwargs: Client())
    monkeypatch.setattr(main, "_tv_probe_cache", {"ts": 0.0, "result": None})

    projected = asyncio.run(main._probe_tradingview_webhook())
    assert projected["last_ping"] is None
    assert projected["pending_alerts"] == 0

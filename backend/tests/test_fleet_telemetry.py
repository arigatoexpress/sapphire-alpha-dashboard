from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fleet_telemetry import FleetTelemetryStore


class PoisonPersistence:
    def accept(
        self,
        snapshot: dict[str, Any],
        *,
        nonce: str,
        received_at: float,
    ) -> None:
        raise AssertionError("not used")

    def select(
        self,
        *,
        received_before: float,
    ) -> tuple[float, dict[str, Any]]:
        return received_before, {
            "version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "sequence": 7,
            "leases": [],
            "gates": [],
            "counts": {"leases": 0, "gates_open": 0},
            "unexpected": "/private/fleet-lease.db",
        }

    def has_history(self) -> bool:
        return True

    def reset(self) -> None:
        return None


def test_durable_read_revalidates_and_fails_closed_on_poisoned_storage():
    store = FleetTelemetryStore(PoisonPersistence())
    assert store.get() is None

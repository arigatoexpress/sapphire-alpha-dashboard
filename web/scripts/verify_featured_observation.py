#!/usr/bin/env python3
"""Verify integrity of one privacy-safe public market-observation projection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OBSERVATION = (
    Path(__file__).resolve().parents[1]
    / "content"
    / "evidence"
    / "rhchain-aapl-20260808.json"
)
EXPECTED_SHA256 = "ee712e4ecee980a602fb2b679c52ba555964ae7b281799d0672c3e10de259a04"
EXPECTED_KEYS = {
    "schema",
    "observed_at",
    "asset_pair",
    "chain",
    "range",
    "observations",
    "evidence",
    "finality",
    "authority",
    "limitations",
}
FORBIDDEN_KEYS = {
    "address",
    "sender",
    "recipient",
    "wallet",
    "balance",
    "position",
    "chat_id",
    "user_id",
}


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _walk_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _walk_keys(item)}
    return set()


def main() -> int:
    raw = OBSERVATION.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise SystemExit("featured observation bytes do not match the reviewed digest")

    record = json.loads(raw)
    if set(record) != EXPECTED_KEYS:
        raise SystemExit("featured observation schema drift")
    if _walk_keys(record) & FORBIDDEN_KEYS:
        raise SystemExit("featured observation contains a forbidden privacy key")
    if record["schema"] != "sapphire.public-observation/v1":
        raise SystemExit("featured observation version mismatch")
    if record["chain"] != {
        "name": "Robinhood Chain",
        "chain_id": 4663,
        "source_url": "https://docs.robinhood.com/chain/connecting/",
    }:
        raise SystemExit("featured observation chain identity mismatch")
    if record["range"] != {"start_block": 31371085, "end_block": 31371092}:
        raise SystemExit("featured observation range mismatch")
    if record["observations"] != {
        "validated_pools": 6,
        "events": 1,
        "event_types": ["v3_swap"],
    }:
        raise SystemExit("featured observation counts mismatch")
    if record["finality"] != {
        "outcome": "reconciled",
        "depth": 32,
        "economically_finalized": False,
    }:
        raise SystemExit("featured observation finality mismatch")
    if record["authority"] != {
        "research": "observation_only",
        "signal": False,
        "ranking": False,
        "trade": False,
    }:
        raise SystemExit("featured observation authority mismatch")
    if any(
        not isinstance(value, str) or len(value) != 64
        for value in record["evidence"].values()
    ):
        raise SystemExit("featured observation evidence hash mismatch")

    print(json.dumps({"status": "ok", "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

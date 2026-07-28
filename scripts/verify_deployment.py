#!/usr/bin/env python3
"""Read-only proof that one deployed revision serves the expected source and UI."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


Fetch = Callable[[str], tuple[int, str]]

PAGE_CONTRACTS = {
    "public_home": ("/", 'id="public-title"'),
    "operator_home": ("/dashboard", '<div id="root"></div>'),
    "calibration_report": (
        "/research/calibration-2026-07-27/",
        "<title>Learning loop — wins, losses, calibration",
    ),
}


def _fetch(url: str) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "sapphire-deploy-verifier/1"})
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - caller supplies base URL
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def verify(
    base_url: str,
    expected_identity: dict[str, Any],
    fetch: Fetch = _fetch,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    checks: dict[str, bool] = {}
    status, body = fetch(f"{base}/api/build")
    checks["build_endpoint"] = status == 200
    try:
        build = json.loads(body)
    except json.JSONDecodeError:
        build = {}
    checks["build_identity_exact"] = build == expected_identity

    for name, (path, marker) in PAGE_CONTRACTS.items():
        page_status, page = fetch(f"{base}{path}")
        checks[name] = page_status == 200 and marker in page

    result: dict[str, Any] = {
        "ok": all(checks.values()),
        "expected_identity_sha256": hashlib.sha256(
            json.dumps(
                expected_identity, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        "checks": checks,
    }
    # Actual runtime identifiers are useful evidence only after every check
    # passes. A failure result is deliberately predicate-only so a drifted
    # environment or future canary can never be reflected into logs.
    if result["ok"]:
        result.update(
            deployed_sha=expected_identity["source_sha"],
            build_id=expected_identity["build_id"],
            runtime_revision=expected_identity["runtime_revision"],
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "expected_identity",
        type=Path,
        help="canonical JSON containing the exact expected /api/build payload",
    )
    parser.add_argument("--base-url", default="https://sapphirealpha.xyz")
    args = parser.parse_args()

    try:
        raw = args.expected_identity.read_bytes()
        expected = json.loads(raw)
        if (
            not isinstance(expected, dict)
            or raw
            != (
                json.dumps(
                    expected,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                + "\n"
            ).encode()
        ):
            raise ValueError("non-canonical expected identity")
        result = verify(args.base_url, expected)
    except Exception:
        result = {
            "ok": False,
            "error": "deployment contract mismatch",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

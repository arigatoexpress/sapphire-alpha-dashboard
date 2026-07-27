#!/usr/bin/env python3
"""Read-only proof that one deployed revision serves the expected source and UI."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from typing import Any
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
    with urlopen(request, timeout=15) as response:  # noqa: S310 - caller supplies base URL
        return response.status, response.read().decode("utf-8")


def verify(base_url: str, expected_sha: str, fetch: Fetch = _fetch) -> dict[str, Any]:
    base = base_url.rstrip("/")
    checks: dict[str, bool] = {}
    status, body = fetch(f"{base}/api/build")
    checks["build_endpoint"] = status == 200
    try:
        build = json.loads(body)
    except json.JSONDecodeError:
        build = {}
    checks["source_sha"] = build.get("source_sha") == expected_sha
    checks["complete"] = build.get("complete") is True

    surfaces = build.get("surfaces") if isinstance(build.get("surfaces"), dict) else {}
    for name in ("operator", "public"):
        surface = surfaces.get(name) if isinstance(surfaces.get(name), dict) else {}
        digest = surface.get("manifest_sha256")
        checks[f"{name}_manifest"] = (
            isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and surface.get("asset_count", 0) > 0
        )

    for name, (path, marker) in PAGE_CONTRACTS.items():
        page_status, page = fetch(f"{base}{path}")
        checks[name] = page_status == 200 and marker in page

    return {
        "ok": all(checks.values()),
        "expected_sha": expected_sha,
        "deployed_sha": build.get("source_sha"),
        "build_id": build.get("build_id"),
        "runtime_revision": build.get("runtime_revision"),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected_sha", help="exact 40- or 64-character source SHA")
    parser.add_argument("--base-url", default="https://sapphirealpha.xyz")
    args = parser.parse_args()

    result = verify(args.base_url, args.expected_sha)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

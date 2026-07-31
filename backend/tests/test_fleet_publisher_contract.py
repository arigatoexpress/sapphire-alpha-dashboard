from __future__ import annotations

import plistlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLIST = ROOT / "infra/com.sapphire.fleet-telemetry-publisher.plist"
RUNNER = ROOT / "telemetry/run_fleet_publisher.sh"


def test_fleet_publisher_uses_only_the_sanitized_export_boundary():
    runner = RUNNER.read_text(encoding="utf-8")
    assert "export --sanitized --out" in runner
    assert "/api/v1/fleet/telemetry" in runner
    assert "TELEMETRY_INGEST_SECRET" in runner
    assert "fleet-lease.db" not in runner


def test_fleet_publisher_launchagent_has_current_cadence_and_explicit_path():
    with PLIST.open("rb") as handle:
        config = plistlib.load(handle)
    assert config["Label"] == "com.sapphire.fleet-telemetry-publisher"
    assert config["StartInterval"] == 60
    assert config["RunAtLoad"] is True
    assert config["ProgramArguments"] == [
        "/Users/aribs/Code/sapphire-alpha-dashboard/telemetry/run_fleet_publisher.sh"
    ]
    assert config["EnvironmentVariables"]["PATH"].startswith("/opt/homebrew/bin:")

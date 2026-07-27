"""The retired interface must stay deleted while live visual contracts remain."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_retired_component_closure_is_absent():
    retired = [
        "frontend/src/components/DecisionCockpit.tsx",
        "frontend/src/components/EvidenceWatch.tsx",
        "frontend/src/components/LiveClock.tsx",
        "frontend/src/components/MarketAperture.tsx",
        "frontend/src/components/SignalRoutes.tsx",
        "frontend/src/components/icons.tsx",
        "frontend/src/components/ui.tsx",
        "web/src/components/MachineRoom.tsx",
        "web/src/components/MarketAperture.tsx",
        "web/src/lib/machineRoom.ts",
    ]
    assert [path for path in retired if (ROOT / path).exists()] == []


def test_retired_css_systems_are_absent_and_live_signatures_remain():
    shared = (ROOT / "shared/theme.css").read_text(encoding="utf-8")
    web = (ROOT / "web/src/app/globals.css").read_text(encoding="utf-8")

    for selector in (
        ".market-aperture",
        ".aperture-",
        ".optic-",
        ".machine-drawer",
        ".mc-",
        ".mr-",
        ".home-pro",
        ".home-hero",
        ".home-card",
    ):
        assert selector not in shared + web

    for selector in (
        ".status-chip",
        ".viz-concepts",
        ".home-viz-row",
        ".proof-spine",
        ".prose-report",
        ".public-observatory",
    ):
        assert selector in shared + web

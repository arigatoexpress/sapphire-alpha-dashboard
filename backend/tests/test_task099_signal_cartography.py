"""Task 099 red goldens: static source contracts for signal cartography.

These assert design-token presence, route inventory, and forbidden claim patterns
in source and built artifacts when available. They must fail on exact Task-093
base source and pass only after the blue-hour rebuild.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
THEME = ROOT / "shared" / "theme.css"
WEB_NAV = ROOT / "web" / "src" / "components" / "Nav.tsx"
WEB_HOME = ROOT / "web" / "src" / "components" / "MissionControl.tsx"
WEB_PAGE = ROOT / "web" / "src" / "app" / "page.tsx"
FE_APP = ROOT / "frontend" / "src" / "App.tsx"
SITEMAP = ROOT / "web" / "src" / "app" / "sitemap.ts"

REQUIRED_COLORS = {
    "observatory-ink": "#102A36",
    "atlas-blue": "#174A67",
    "glacier": "#F3F8F7",
    "skywash": "#D8EBEE",
    "signal-coral": "#B54632",
    "caution-gold": "#8A6100",
}

PUBLIC_ROUTES = [
    "/",
    "/architecture/",
    "/trading/",
    "/security/",
    "/proof/",
    "/onchain/",
    "/research/",
    "/about/",
]


def test_shared_theme_defines_blue_hour_tokens():
    text = THEME.read_text(encoding="utf-8")
    for name, hex_value in REQUIRED_COLORS.items():
        assert re.search(
            rf"--color-{re.escape(name)}\s*:\s*{re.escape(hex_value)}",
            text,
            re.I,
        ), f"missing token --color-{name}: {hex_value}"


def test_body_canvas_is_glacier_not_void():
    text = THEME.read_text(encoding="utf-8")
    body = re.search(r"body\s*\{([^}]+)\}", text, re.S)
    assert body, "body rule missing in shared theme"
    block = body.group(1)
    assert "var(--color-glacier)" in block
    assert "var(--color-void)" not in block
    assert "#071018" not in block


def test_type_roles_newsreader_space_grotesk_jetbrains():
    text = THEME.read_text(encoding="utf-8")
    assert re.search(r"--font-display:[^;]*Newsreader", text, re.I)
    assert re.search(r"--font-body:[^;]*Space Grotesk", text, re.I)
    assert re.search(r"--font-mono:[^;]*JetBrains Mono", text, re.I)


def test_public_nav_primary_paths():
    nav = WEB_NAV.read_text(encoding="utf-8")
    assert "/research/" in nav
    assert "Research" in nav
    assert "/architecture/" in nav
    assert "Systems" in nav or "System" in nav
    assert "/dashboard" in nav
    assert "Live desk" in nav or "Live Desk" in nav


def test_route_inventory_remains_in_sitemap():
    sm = SITEMAP.read_text(encoding="utf-8")
    for path in PUBLIC_ROUTES:
        if path == "/":
            assert "'/'" in sm or '"/"' in sm
        else:
            assert path in sm, f"route missing from sitemap: {path}"


def test_public_home_signal_cartography_copy():
    # Home may be MissionControl client component or page.tsx — check both.
    sources = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (WEB_HOME, WEB_PAGE)
        if p.exists()
    )
    assert re.search(r"A system that shows its work", sources, re.I)
    assert re.search(r"Evidence horizon", sources, re.I)
    assert "Read research" in sources or "Read Research" in sources
    assert "System map" in sources or "System Map" in sources
    assert "data-evidence-state" in sources


def test_operator_current_decision_band():
    app = FE_APP.read_text(encoding="utf-8")
    assert re.search(r"CURRENT DECISION", app, re.I)
    assert re.search(r"Evidence horizon", app, re.I)


def test_no_forbidden_placeholder_or_control_strings_in_surfaces():
    surfaces = []
    for path in (
        WEB_HOME,
        WEB_PAGE,
        FE_APP,
        ROOT / "web" / "src" / "components" / "Nav.tsx",
        ROOT / "web" / "src" / "components" / "Footer.tsx",
    ):
        if path.exists():
            surfaces.append(path.read_text(encoding="utf-8"))
    blob = "\n".join(surfaces)
    for forbidden in (
        "Book a demo",
        "Join waitlist",
        "force-clear",
        "Force clear",
        "Connect wallet",
        "Place order",
        "lorem ipsum",
        "TODO metric",
    ):
        assert forbidden.lower() not in blob.lower(), f"forbidden string present: {forbidden}"


def test_reduced_motion_contract_present():
    theme = THEME.read_text(encoding="utf-8")
    fe_css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
    web_css = (ROOT / "web" / "src" / "app" / "globals.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in theme + fe_css + web_css

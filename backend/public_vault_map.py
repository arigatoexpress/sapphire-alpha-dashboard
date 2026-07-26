"""PII-free public projection of the local Knowledge vault.

Public labels, topics, and relationships come from the fixed taxonomy below.
The vault contributes no runtime data at all: not content, names, paths,
timestamps, mount state, or counts.  A private filesystem fact therefore has
no route into the response.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final


_CLUSTERS: Final = (
    {
        "id": "systems",
        "name": "Systems engineering",
        "one_liner": "How autonomous software is designed, tested, and operated.",
        "topics": ("architecture", "automation", "verification"),
        "roots": (
            "1-Projects",
            "2-Areas/ai-ml",
            "2-Areas/data-engineering",
            "2-Areas/ops",
        ),
    },
    {
        "id": "markets",
        "name": "Markets and risk",
        "one_liner": "Research about markets, execution, and ways a thesis can fail.",
        "topics": ("market structure", "risk", "execution"),
        "roots": (
            "2-Areas/trading",
            "2-Areas/finance",
            "2-Areas/defi-research",
            "2-Areas/blockchain",
            "2-Areas/macro",
            "2-Areas/austrian-economics",
        ),
    },
    {
        "id": "resilience",
        "name": "Security and resilience",
        "one_liner": "Failure analysis, defensive design, and operational safety.",
        "topics": ("security", "reliability", "failure analysis"),
        "roots": (
            "2-Areas/security",
            "2-Areas/defense-analysis",
            "2-Areas/drones",
        ),
    },
    {
        "id": "sources",
        "name": "Source library",
        "one_liner": "Papers and distilled references used to check new claims.",
        "topics": ("papers", "references", "evidence"),
        "roots": (
            "3-Resources/papers",
            "3-Resources/Distilled-Sources",
            "3-Resources/books",
        ),
    },
    {
        "id": "world-model",
        "name": "World model",
        "one_liner": "Cross-domain concepts connected into reusable explanations.",
        "topics": ("synthesis", "causal models", "cross-domain links"),
        "roots": ("5-World-Model",),
    },
)

_LINKS: Final = (
    {"source": "sources", "target": "world-model", "relationship": "grounds"},
    {"source": "world-model", "target": "systems", "relationship": "informs"},
    {"source": "world-model", "target": "markets", "relationship": "informs"},
    {"source": "resilience", "target": "systems", "relationship": "tests"},
    {"source": "resilience", "target": "markets", "relationship": "constrains"},
)


def generate(vault_root: Path) -> dict[str, Any]:
    """Return the stable public taxonomy without inspecting ``vault_root``.

    The argument remains in the API so a future authenticated or paid
    projection can share the call boundary.  The public implementation is
    deliberately data-independent and constant-time.
    """

    del vault_root
    clusters = [
        {
            "id": cluster["id"],
            "name": cluster["name"],
            "one_liner": cluster["one_liner"],
            "topics": list(cluster["topics"]),
        }
        for cluster in _CLUSTERS
    ]
    return {
        "schema_version": 1,
        "access": "public",
        "clusters": clusters,
        "links": [dict(link) for link in _LINKS],
        "totals": {"clusters": len(clusters)},
    }

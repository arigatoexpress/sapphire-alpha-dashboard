"""Public Knowledge-map projection.

The raw visual map contains personal note titles and remains authenticated.
This endpoint exposes only a fixed public taxonomy.  The
fixture deliberately puts identifying material in both filenames and bodies so
the test proves the generator never derives output from vault state.
"""

from __future__ import annotations

import json
from pathlib import Path

import main
import public_vault_map
from fastapi.testclient import TestClient


def _seed(root: Path) -> None:
    files = {
        "2-Areas/ai-ml/Private Person - employer project.md": "phone 555-0109",
        "2-Areas/trading/account-1234.md": "wallet 0xdeadbeef",
        "2-Areas/security/Home Address.md": "123 Private Street",
        "3-Resources/papers/Secret Person Thesis.md": "personal date 1990-01-01",
        "5-World-Model/Synthesis/Private Family Map.md": "family member",
        # Deliberately outside the allowlisted roots.
        "0-Inbox/Extremely Private Inbox.md": "must never affect the projection",
    }
    for relative, body in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def test_projection_is_fixed_taxonomy_not_vault_derived(tmp_path):
    _seed(tmp_path)

    projection = public_vault_map.generate(tmp_path)
    encoded = json.dumps(projection, sort_keys=True)

    assert projection["schema_version"] == 1
    assert projection["access"] == "public"
    assert [cluster["id"] for cluster in projection["clusters"]] == [
        "systems",
        "markets",
        "resilience",
        "sources",
        "world-model",
    ]
    assert projection["totals"] == {"clusters": 5}

    forbidden = (
        "Private Person",
        "employer",
        "account-1234",
        "0xdeadbeef",
        "Home Address",
        "Private Street",
        "Secret Person",
        "1990-01-01",
        "Private Family",
        "Extremely Private",
        str(tmp_path),
        ".md",
        "/Users/",
        "\\Users\\",
    )
    assert all(value not in encoded for value in forbidden)


def test_projection_does_not_inspect_the_filesystem(tmp_path, monkeypatch):
    _seed(tmp_path)

    def fail(*_args, **_kwargs):
        raise AssertionError("the public projection inspected private filesystem state")

    monkeypatch.setattr(Path, "read_text", fail)
    monkeypatch.setattr(Path, "is_dir", fail)
    monkeypatch.setattr(Path, "rglob", fail)
    projection = public_vault_map.generate(tmp_path)

    assert projection["totals"] == {"clusters": 5}


def test_projection_is_identical_when_the_vault_is_missing(tmp_path):
    present = public_vault_map.generate(tmp_path)
    missing = public_vault_map.generate(tmp_path / "not-mounted")

    assert missing == present


def test_public_endpoint_is_anonymous_and_raw_map_stays_private(tmp_path, monkeypatch):
    _seed(tmp_path)
    monkeypatch.setattr(main, "_KNOWLEDGE_ROOT", tmp_path)
    client = TestClient(main.app)

    response = client.get("/api/v1/vault-map")

    assert response.status_code == 200
    assert response.json()["totals"] == {"clusters": 5}
    assert client.get("/vault/rag-map").status_code == 401

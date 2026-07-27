"""Build identity must describe the bytes actually served by the container."""

from hashlib import sha256

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_build_identity_binds_source_runtime_and_both_frontends(tmp_path, monkeypatch):
    operator_dir = tmp_path / "frontend"
    public_dir = tmp_path / "web"
    operator_dir.mkdir()
    public_dir.mkdir()
    operator = operator_dir / "index.html"
    public = public_dir / "index.html"
    operator.write_bytes(b"<main>operator</main>")
    public.write_bytes(b"<main>public</main>")
    (operator_dir / "app.js").write_bytes(b"operator-js")
    (public_dir / "site.css").write_bytes(b"public-css")

    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", operator_dir)
    monkeypatch.setattr(main, "_WEB_OUT_DIR", public_dir)
    monkeypatch.setenv("SAPPHIRE_BUILD_SHA", "a" * 40)
    monkeypatch.setenv("SAPPHIRE_BUILD_ID", "build-123")
    monkeypatch.setenv("K_SERVICE", "sapphire-alpha-dashboard")
    monkeypatch.setenv("K_REVISION", "sapphire-alpha-dashboard-00042-abc")
    main._build_identity.cache_clear()

    identity = main._build_identity()

    assert identity["schema"] == 1
    assert identity["source_sha"] == "a" * 40
    assert identity["build_id"] == "build-123"
    assert identity["runtime_service"] == "sapphire-alpha-dashboard"
    assert identity["runtime_revision"] == "sapphire-alpha-dashboard-00042-abc"
    assert identity["surfaces"]["operator"]["entrypoint_url"] == "/dashboard"
    assert (
        identity["surfaces"]["operator"]["entrypoint_sha256"]
        == sha256(operator.read_bytes()).hexdigest()
    )
    assert identity["surfaces"]["operator"]["asset_count"] == 2
    assert identity["surfaces"]["operator"]["manifest_sha256"]
    assert identity["surfaces"]["public"]["entrypoint_url"] == "/"
    assert (
        identity["surfaces"]["public"]["entrypoint_sha256"]
        == sha256(public.read_bytes()).hexdigest()
    )
    assert identity["surfaces"]["public"]["asset_count"] == 2
    assert identity["surfaces"]["public"]["manifest_sha256"]
    assert identity["complete"] is True


def test_surface_manifest_is_deterministic_and_sensitive_to_asset_bytes(tmp_path):
    (tmp_path / "index.html").write_bytes(b"index")
    (tmp_path / "z.js").write_bytes(b"z")
    nested = tmp_path / "assets"
    nested.mkdir()
    asset = nested / "a.css"
    asset.write_bytes(b"a")

    first = main._surface_manifest(tmp_path, "/")
    second = main._surface_manifest(tmp_path, "/")
    asset.write_bytes(b"changed")
    changed = main._surface_manifest(tmp_path, "/")

    assert first == second
    assert first["asset_count"] == 3
    assert first["manifest_sha256"] != changed["manifest_sha256"]


def test_surface_manifest_ignores_symlinks_that_escape_the_surface(tmp_path):
    root = tmp_path / "surface"
    root.mkdir()
    (root / "index.html").write_bytes(b"index")
    outside = tmp_path / "private.txt"
    outside.write_bytes(b"must-not-be-hashed")
    (root / "escape.txt").symlink_to(outside)

    manifest = main._surface_manifest(root, "/")

    assert manifest["asset_count"] == 1
    assert manifest["entrypoint_sha256"] == sha256(b"index").hexdigest()


def test_build_identity_is_explicitly_incomplete_without_baked_metadata(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path / "missing-operator")
    monkeypatch.setattr(main, "_WEB_OUT_DIR", tmp_path / "missing-public")
    for name in ("SAPPHIRE_BUILD_SHA", "SAPPHIRE_BUILD_ID", "K_SERVICE", "K_REVISION"):
        monkeypatch.delenv(name, raising=False)
    main._build_identity.cache_clear()

    identity = main._build_identity()

    assert identity["source_sha"] == "unknown"
    assert identity["build_id"] == "unknown"
    assert identity["runtime_service"] == "local"
    assert identity["runtime_revision"] == "local"
    assert identity["surfaces"]["operator"]["entrypoint_sha256"] is None
    assert identity["surfaces"]["operator"]["asset_count"] == 0
    assert identity["surfaces"]["operator"]["manifest_sha256"] is None
    assert identity["surfaces"]["public"]["entrypoint_sha256"] is None
    assert identity["complete"] is False


def test_public_build_endpoint_and_health_share_the_same_identity(monkeypatch):
    identity = {
        "schema": 1,
        "source_sha": "b" * 40,
        "build_id": "build-456",
        "runtime_service": "sapphire-alpha-dashboard",
        "runtime_revision": "sapphire-alpha-dashboard-00043-def",
        "surfaces": {
            "operator": {
                "entrypoint_url": "/dashboard",
                "entrypoint_sha256": "c" * 64,
                "asset_count": 10,
                "manifest_sha256": "e" * 64,
            },
            "public": {
                "entrypoint_url": "/",
                "entrypoint_sha256": "d" * 64,
                "asset_count": 20,
                "manifest_sha256": "f" * 64,
            },
        },
        "complete": True,
    }
    monkeypatch.setattr(main, "_build_identity", lambda: identity)

    build_response = client.get("/api/build")
    health_response = client.get("/api/health")

    assert build_response.status_code == 200
    assert build_response.json() == identity
    assert build_response.headers["Cache-Control"] == "no-store"
    assert health_response.status_code == 200
    assert "build" not in health_response.json()


def test_build_identity_rejects_arbitrary_environment_content(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_FRONTEND_DIST_DIR", tmp_path)
    monkeypatch.setattr(main, "_WEB_OUT_DIR", tmp_path)
    monkeypatch.setenv("SAPPHIRE_BUILD_SHA", "not-a-commit")
    monkeypatch.setenv("SAPPHIRE_BUILD_ID", "bad value with spaces")
    monkeypatch.setenv("K_SERVICE", "../../secret")
    monkeypatch.setenv("K_REVISION", "revision\ninjection")
    main._build_identity.cache_clear()

    identity = main._build_identity()

    assert set(identity) == {
        "schema",
        "source_sha",
        "build_id",
        "runtime_service",
        "runtime_revision",
        "surfaces",
        "complete",
    }
    assert identity["source_sha"] == "unknown"
    assert identity["build_id"] == "unknown"
    assert identity["runtime_service"] == "local"
    assert identity["runtime_revision"] == "local"
    assert identity["complete"] is False


def test_build_identity_hashes_each_surface_once_per_process(monkeypatch):
    calls = []

    def fake_manifest(_root, entrypoint_url):
        calls.append(entrypoint_url)
        return {
            "entrypoint_url": entrypoint_url,
            "entrypoint_sha256": "a" * 64,
            "asset_count": 1,
            "manifest_sha256": "b" * 64,
        }

    monkeypatch.setattr(main, "_surface_manifest", fake_manifest)
    monkeypatch.setenv("SAPPHIRE_BUILD_SHA", "c" * 40)
    monkeypatch.setenv("SAPPHIRE_BUILD_ID", "build-789")
    monkeypatch.setenv("K_REVISION", "sapphire-alpha-dashboard-00044-ghi")
    main._build_identity.cache_clear()

    first = main._build_identity()
    second = main._build_identity()

    assert first is second
    assert calls == ["/dashboard", "/"]

"""Golden evals for measured link telemetry.

The load-bearing property across this file is a negative one: a link that cannot
be measured must publish `None`, and no code path may substitute a plausible
number for it. Every assertion here was mutation-tested by making the
implementation return a default instead — the notes name which mutation each one
catches, because a test that passes against both branches is decoration.

No test touches the network. Every probe takes its clock and its opener as an
argument, so what is under test is the measurement logic, not the wifi.
"""

from __future__ import annotations

import json
import plistlib
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

from live_telemetry import TelemetryValidationError, validate_snapshot
from telemetry import merged_collector, probes, win_collector
from telemetry.collector import (
    DESK_CYCLE_STALE_AFTER_SECONDS,
    Sources,
    _desk_insert_rate,
    _presence_health,
    build_snapshot,
    configured_latencies,
    push,
)


NOW = 1_785_000_000.0
DESK_CYCLE_PLIST = Path.home() / "Library" / "LaunchAgents" / "com.ari.deskos-cycle.plist"


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


class _FakeResponse:
    def __init__(self, payload: bytes = b"ok") -> None:
        self._payload = payload

    def read(self, size: int | None = None) -> bytes:
        return self._payload if size is None else self._payload[:size]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _StepClock:
    """A clock that advances a fixed amount on every reading."""

    def __init__(self, step_s: float) -> None:
        self._step = step_s
        self._value = 0.0

    def __call__(self) -> float:
        current = self._value
        self._value += self._step
        return current


# ---------------------------------------------------------------- probes: latency


def test_http_latency_is_the_measured_round_trip():
    clock = _StepClock(0.0125)
    measured = probes.http_latency_ms(
        "https://example.invalid/healthz",
        opener=lambda *_a, **_k: _FakeResponse(),
        clock=clock,
    )
    assert measured == 12.5


def test_unreachable_endpoint_is_none_not_the_timeout():
    """Mutation: `return timeout * 1000` on failure. A failed probe is not a slow
    probe, and publishing the timeout would render as a real, terrible latency."""

    def explode(*_args, **_kwargs):
        raise OSError("host is down")

    assert probes.http_latency_ms("https://example.invalid/", opener=explode) is None


def test_empty_endpoint_is_none():
    assert probes.http_latency_ms("", opener=lambda *_a, **_k: _FakeResponse()) is None


def test_gateway_latency_times_the_tier_the_router_would_pick():
    health = json.dumps(
        {
            "gateway": "ok",
            "tiers": [
                {"name": "home_lan", "url": "http://tier-one.invalid:11434", "healthy": False},
                {"name": "home_ts", "url": "http://tier-two.invalid:11434", "healthy": True},
                {"name": "local", "url": "http://tier-three.invalid:11434", "healthy": True},
            ],
        }
    ).encode()
    seen: list[str] = []

    def opener(request, **_kwargs):
        seen.append(request.full_url)
        return _FakeResponse(health if request.full_url.endswith("/healthz") else b"ok")

    measured = probes.gateway_route_latency_ms(
        "http://gateway.invalid/healthz", opener=opener, clock=_StepClock(0.004)
    )
    # First healthy tier in configured order, exactly as TierRouter selects.
    assert seen[-1] == "http://tier-two.invalid:11434"
    assert measured == 4.0


def test_gateway_with_no_healthy_tier_is_none():
    """Mutation: fall back to timing the first tier regardless of health. With
    nothing routable there is no latency, and the local fallback's number is not
    the GPU's."""
    health = json.dumps({"tiers": [{"name": "home_lan", "url": "http://x.invalid", "healthy": False}]}).encode()
    assert (
        probes.gateway_route_latency_ms(
            "http://gateway.invalid/healthz",
            opener=lambda *_a, **_k: _FakeResponse(health),
            clock=_StepClock(0.001),
        )
        is None
    )


def test_gateway_unreachable_is_none():
    def explode(*_args, **_kwargs):
        raise OSError("connection refused")

    assert probes.gateway_route_latency_ms("http://gateway.invalid/healthz", opener=explode) is None


# ------------------------------------------------------------------ probes: rates


def _epoch_parser(line: str) -> float | None:
    try:
        return float(line.split()[0])
    except (ValueError, IndexError):
        return None


def test_log_rate_counts_only_the_window():
    lines = [
        f"{NOW - 600} old",
        f"{NOW - 120} inside",
        f"{NOW - 30} inside",
        f"{NOW + 5} future",
    ]
    assert probes.log_rate_per_min(lines, now=NOW, parse_ts=_epoch_parser, window_s=300) == 0.4


def test_empty_log_is_a_measured_zero_not_a_blank():
    """An append-only source we can read, with nothing in the window, observed
    zero. That is a fact, and it is different from having no source."""
    assert probes.log_rate_per_min([], now=NOW, parse_ts=_epoch_parser) == 0.0


def test_missing_log_is_none_not_zero():
    """Mutation: `if lines is None: lines = []`. That turns "there is no log
    here" into "nothing happened", which is a claim we did not measure."""
    assert probes.log_rate_per_min(None, now=NOW, parse_ts=_epoch_parser) is None


def test_read_tail_lines_distinguishes_missing_from_empty(tmp_path):
    assert probes.read_tail_lines(tmp_path / "nope.log") is None
    (tmp_path / "empty.log").write_text("", encoding="utf-8")
    assert probes.read_tail_lines(tmp_path / "empty.log") == []


def test_read_tail_lines_drops_the_partial_first_line(tmp_path):
    target = tmp_path / "big.log"
    target.write_text("".join(f"line-{index}\n" for index in range(4000)), encoding="utf-8")
    lines = probes.read_tail_lines(target, max_bytes=200)
    assert lines and all(line.startswith("line-") for line in lines)
    assert lines[-1] == "line-3999"


def test_directory_rate_counts_recent_arrivals(tmp_path):
    drop = tmp_path / "done"
    drop.mkdir()
    for index, age in enumerate((10, 60, 4000)):
        target = drop / f"task-{index}.json"
        target.write_text("{}", encoding="utf-8")
        import os

        os.utime(target, (NOW - age, NOW - age))
    assert probes.directory_event_rate_per_min(drop, now=NOW, window_s=300) == 0.4


def test_missing_directory_is_none(tmp_path):
    assert probes.directory_event_rate_per_min(tmp_path / "absent", now=NOW) is None


def test_snapshot_measurement_refuses_to_speak_for_a_stale_file():
    """Mutation: drop the age check and always return the value. A state file
    reports what was true when it was written; serving it as current is an
    extrapolation wearing a measurement's clothes."""
    assert probes.snapshot_measurement(598, source_age_s=5, window_s=300) == 598.0
    assert probes.snapshot_measurement(598, source_age_s=3600, window_s=300) is None
    assert probes.snapshot_measurement(None, source_age_s=1, window_s=300) is None


# ----------------------------------------------------------- collector: the links


def _sources(tmp_path: Path, **overrides) -> Sources:
    defaults = {
        "rh_health": _write(tmp_path / "health.json", {"generated_ts": NOW - 10, "overall": "healthy", "agents": []}),
        "rh_feed": _write(tmp_path / "feed.json", {"updated": NOW - 5, "msgs_per_min": 598, "feed_lag_s": 0.38}),
        "memes": _write(tmp_path / "memes.json", {"updated": NOW - 5}),
        "paper": _write(tmp_path / "paper.json", {"updated": NOW - 5}),
        "gpu": _write(tmp_path / "gpu.json", {"last_check": _iso(NOW - 10), "status": "up", "services": {"ollama": 1}}),
        "desk_cycle": _write(
            tmp_path / "desk.json",
            {
                "started_at": _iso(NOW - 3627),
                "finished_at": _iso(NOW - 3600),
                "status": "ok",
                "totals": {"inserted": 318, "errors": 0},
            },
        ),
        "agent_presence": None,
    }
    defaults.update(overrides)
    return Sources(**defaults)


def _links(snapshot: dict) -> dict[tuple[str, str], dict]:
    return {(link["source"], link["target"]): link for link in snapshot["links"]}


def test_markets_link_publishes_rate_but_not_one_way_feed_lag_as_latency(tmp_path):
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)
    markets = _links(snapshot)[("intelligence", "markets")]
    # feed_lag_s is timestamp lag from the source, not a timed request round
    # trip. Mutation: multiply it by 1000 and put it in latency_ms.
    assert markets["latency_ms"] is None
    assert markets["event_rate"] == 598.0


def test_unmeasurable_links_publish_none_not_a_default(tmp_path):
    """THE load-bearing assertion. Mutation: give any of these a numeric default
    (`0.0`, `len(agents)`, `service_count * 8`) and this fails. Verified by doing
    exactly that — see the report."""
    snapshot = build_snapshot(_sources(tmp_path), now=NOW, link_latencies={})
    links = _links(snapshot)

    assert links[("public-edge", "orchestration")]["latency_ms"] is None
    assert links[("public-edge", "orchestration")]["event_rate"] is None
    assert links[("orchestration", "gpu-compute")]["latency_ms"] is None
    assert links[("orchestration", "gpu-compute")]["event_rate"] is None
    assert links[("gpu-compute", "intelligence")]["latency_ms"] is None
    assert links[("intelligence", "archive")]["latency_ms"] is None


def test_a_stale_feed_withdraws_its_numbers_instead_of_repeating_them(tmp_path):
    """Mutation: keep publishing msgs_per_min regardless of feed age. A feed
    state written an hour ago cannot tell you the rate right now."""
    stale = _write(tmp_path / "stale-feed.json", {"updated": NOW - 3600, "msgs_per_min": 598, "feed_lag_s": 0.38})
    snapshot = build_snapshot(_sources(tmp_path, rh_feed=stale), now=NOW)
    markets = _links(snapshot)[("intelligence", "markets")]
    assert markets["latency_ms"] is None
    assert markets["event_rate"] is None


def test_desk_insert_rate_is_rows_over_the_cycles_own_clock():
    desk = {"started_at": _iso(NOW - 60), "finished_at": _iso(NOW - 30), "totals": {"inserted": 300}}
    # 300 rows in 30 s of wall clock = 600 rows/min, measured, not modelled.
    assert _desk_insert_rate(desk, desk_age=30) == 600.0


def test_desk_insert_rate_goes_quiet_once_the_cycle_is_history():
    """Mutation: drop the freshness gate. Republishing a three-hour-old burst as
    the current rate is the fabrication this whole change exists to remove."""
    desk = {"started_at": _iso(NOW - 3630), "finished_at": _iso(NOW - 3600), "totals": {"inserted": 300}}
    assert _desk_insert_rate(desk, desk_age=3600) is None


def test_desk_insert_rate_does_not_turn_a_missing_count_into_zero():
    """Mutation: `totals.get("inserted") or 0`. Missing totals do not prove that
    a measured cycle inserted zero rows."""
    desk = {"started_at": _iso(NOW - 60), "finished_at": _iso(NOW - 30), "totals": {}}
    assert _desk_insert_rate(desk, desk_age=30) is None


def test_presence_events_give_a_measured_rate_including_zero(tmp_path):
    quiet = _write(
        tmp_path / "presence.json",
        {
            "agents": [
                {
                    "role": "code",
                    "state": "offline",
                    "verification": "not_applicable",
                    "provider_class": "local GPU",
                    "updated_at": _iso(NOW - 86_000),
                }
            ],
            "events": [{"occurred_at": _iso(NOW - 86_000), "status": "observed", "label": "old"}],
            "source_errors": 0,
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, agent_presence=quiet), now=NOW)
    link = _links(snapshot)[("gpu-compute", "intelligence")]
    # The presence projector re-runs on every append, so an empty window is an
    # observation, not a gap: zero events happened.
    assert link["event_rate"] == 0.0

    busy = _write(
        tmp_path / "busy.json",
        {
            "agents": [
                {
                    "role": "code",
                    "state": "working",
                    "verification": "pending",
                    "provider_class": "local GPU",
                    "updated_at": _iso(NOW - 5),
                }
            ],
            "events": [
                {"occurred_at": _iso(NOW - 20), "status": "observed", "label": "one"},
                {"occurred_at": _iso(NOW - 40), "status": "verified", "label": "two"},
            ],
            "source_errors": 0,
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, agent_presence=busy), now=NOW)
    assert _links(snapshot)[("gpu-compute", "intelligence")]["event_rate"] == 0.4


def test_saturated_presence_window_withdraws_the_rate(tmp_path):
    """The presence projector caps its list at 24. At saturation, events earlier
    in the same five-minute window may have been evicted, so 24/5 is only a lower
    bound and must not be published as the measured rate."""
    saturated = _write(
        tmp_path / "saturated.json",
        {
            "agents": [
                {
                    "role": "code",
                    "state": "working",
                    "verification": "pending",
                    "provider_class": "local GPU",
                    "updated_at": _iso(NOW - 5),
                }
            ],
            "events": [
                {
                    "occurred_at": _iso(NOW - index),
                    "status": "observed",
                    "label": f"event {index}",
                }
                for index in range(24)
            ],
            "source_errors": 0,
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, agent_presence=saturated), now=NOW)
    assert _links(snapshot)[("gpu-compute", "intelligence")]["event_rate"] is None


def test_explicit_complete_presence_window_can_report_at_the_cap(tmp_path):
    complete = _write(
        tmp_path / "complete.json",
        {
            "agents": [
                {
                    "role": "code",
                    "state": "working",
                    "verification": "pending",
                    "provider_class": "local GPU",
                    "updated_at": _iso(NOW - 5),
                }
            ],
            "events": [
                {
                    "occurred_at": _iso(NOW - index),
                    "status": "observed",
                    "label": f"event {index}",
                }
                for index in range(24)
            ],
            "events_window_complete": True,
            "source_errors": 0,
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, agent_presence=complete), now=NOW)
    assert _links(snapshot)[("gpu-compute", "intelligence")]["event_rate"] == 4.8


def test_presence_projector_does_not_forward_arbitrary_personal_prose(tmp_path):
    presence = _write(
        tmp_path / "personal.json",
        {
            "agents": [
                {
                    "role": "owner@example.com",
                    "state": "working",
                    "activity": "Call 303-555-0199",
                    "verification": "pending",
                    "provider_class": "local GPU",
                    "updated_at": _iso(NOW - 5),
                }
            ],
            "events": [
                {
                    "occurred_at": _iso(NOW - 5),
                    "status": "observed",
                    "label": "Ask @private_handle",
                }
            ],
            "source_errors": 0,
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, agent_presence=presence), now=NOW)
    body = json.dumps(snapshot)
    assert "owner@example.com" not in body
    assert "303-555-0199" not in body
    assert "@private_handle" not in body
    assert snapshot["agents"][0]["role"] == "Agent observer"
    assert snapshot["events"][0]["label"] == "Agent activity observed"


def test_no_presence_source_leaves_the_rate_unmeasured(tmp_path):
    """Mutation: the old `len(agents) * 4` fallback. Head-count times a magic
    number is not a rate, and nothing may stand in for the missing source."""
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)
    assert _links(snapshot)[("gpu-compute", "intelligence")]["event_rate"] is None
    assert snapshot["summary"]["active_agents"] is None


def test_missing_market_source_has_no_numeric_age_or_rate(tmp_path):
    missing = tmp_path / "missing-feed.json"
    snapshot = build_snapshot(_sources(tmp_path, rh_feed=missing), now=NOW)
    assert snapshot["markets"]["feed_age_s"] is None
    assert snapshot["markets"]["events_per_min"] is None


def test_configured_latencies_probes_real_endpoints_not_unset_env_vars(monkeypatch):
    """Regression for the original defect: four `SAPPHIRE_*_PROBE` variables that
    were set on no host, so every latency on the site was blank forever."""
    for name in ("SAPPHIRE_EDGE_PROBE", "SAPPHIRE_GPU_GATEWAY_PROBE"):
        monkeypatch.delenv(name, raising=False)
    seen: list[str] = []
    measured = configured_latencies(
        http_probe=lambda url, **_k: seen.append(url) or 11.0,
        gateway_probe=lambda url, **_k: seen.append(url) or 22.0,
    )
    assert all(url for url in seen), "a probe was handed an empty endpoint"
    assert measured == {"public-edge:orchestration": 11.0, "orchestration:gpu-compute": 22.0}


def test_env_overrides_still_win(monkeypatch):
    monkeypatch.setenv("SAPPHIRE_EDGE_PROBE", "https://edge.invalid/healthz")
    seen: list[str] = []
    configured_latencies(
        http_probe=lambda url, **_k: seen.append(url) or 1.0,
        gateway_probe=lambda url, **_k: 2.0,
    )
    assert seen == ["https://edge.invalid/healthz"]


# ------------------------------------------------- collector: the always-red nodes


def test_a_six_hourly_batch_job_is_not_down_three_hours_in(tmp_path):
    """The T2 regression. `com.ari.deskos-cycle` runs on a 21600 s interval while
    `_health` capped every source at 900 s, so orchestration and archive reported
    `down` for 95.8% of every cycle on a source saying `status: ok`."""
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    assert nodes["orchestration"]["status"] == "healthy"
    assert nodes["archive"]["status"] == "healthy"
    # The age is still reported honestly — nothing is being hidden, only the
    # verdict corrected.
    assert nodes["orchestration"]["freshness_s"] == pytest.approx(3600, abs=2)


def test_a_batch_job_that_missed_two_cadences_is_still_down(tmp_path):
    """Mutation: raise the ceiling until nothing ever fires. The check has to
    keep working, or fixing the false red just buys a check that says nothing."""
    dead = _write(
        tmp_path / "dead-desk.json",
        {
            "started_at": _iso(NOW - DESK_CYCLE_STALE_AFTER_SECONDS - 60),
            "finished_at": _iso(NOW - DESK_CYCLE_STALE_AFTER_SECONDS - 30),
            "status": "ok",
            "totals": {"inserted": 1},
        },
    )
    snapshot = build_snapshot(_sources(tmp_path, desk_cycle=dead), now=NOW)
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    assert nodes["orchestration"]["status"] == "down"


def test_desk_threshold_covers_the_real_launchagent_cadence():
    """Parity with the deployed schedule, read from the actual plist rather than
    a copy of the number. Precedent: the publisher cadence test."""
    if not DESK_CYCLE_PLIST.exists():
        pytest.skip("com.ari.deskos-cycle is not installed on this host")
    interval = plistlib.loads(DESK_CYCLE_PLIST.read_bytes()).get("StartInterval")
    assert isinstance(interval, int) and interval > 0
    assert interval * 2 <= DESK_CYCLE_STALE_AFTER_SECONDS, (
        "the desk cycle threshold no longer tolerates one missed run; "
        "shorten the cadence or widen the constant deliberately"
    )


def test_idle_agents_are_not_an_outage():
    """`state: offline` in agent-presence means "no event since the projector's
    window", i.e. no work arrived. Reporting that as `down` pinned the node red
    permanently and left the check unable to tell idle from dead."""
    idle = [{"state": "offline"}, {"state": "offline"}]
    assert _presence_health(idle, source_errors=0) == "healthy"


def test_the_intelligence_check_can_still_fire():
    """Mutation: return "healthy" unconditionally. A green light that cannot turn
    red is the same failure as a red one that never turns green."""
    assert _presence_health([{"state": "blocked"}], source_errors=0) == "degraded"
    assert _presence_health([{"state": "idle"}], source_errors=2) == "degraded"
    assert _presence_health([], source_errors=0) == "unknown"


# ------------------------------------------------------------------ the wire


def test_backend_accepts_and_preserves_an_unmeasured_rate(tmp_path):
    """Mutation: `event_rate or 0.0` in validate_snapshot. Coercion at the
    boundary would silently convert every honest blank into a claim."""
    snapshot = validate_snapshot(build_snapshot(_sources(tmp_path), now=NOW))
    unmeasured = [link for link in snapshot["links"] if link["event_rate"] is None]
    assert unmeasured, "fixture no longer exercises the null path"
    assert all(link["event_rate"] is None for link in unmeasured)


def test_backend_still_rejects_a_junk_rate(tmp_path):
    payload = build_snapshot(_sources(tmp_path), now=NOW)
    payload["links"][0]["event_rate"] = "fast"
    with pytest.raises(TelemetryValidationError):
        validate_snapshot(payload)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://ingest.invalid", code, "rejected", {}, None)


def test_push_sends_the_honest_snapshot_first(tmp_path):
    sent: list[dict] = []
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)
    push(
        snapshot,
        endpoint="https://ingest.invalid",
        secret="s" * 32,
        transport=lambda payload, **_k: sent.append(payload) or {"accepted": True},
    )
    assert len(sent) == 1
    assert any(link["event_rate"] is None for link in sent[0]["links"])


def test_push_never_retries_an_unknown_rate_as_zero(tmp_path):
    """A legacy backend may reject null, but zero means a measured absence of
    traffic. Holding the last accepted snapshot is safer than publishing fiction."""
    sent: list[dict] = []
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)

    def transport(payload, **_kwargs):
        sent.append(payload)
        raise _http_error(422)

    with pytest.raises(urllib.error.HTTPError):
        push(snapshot, endpoint="https://ingest.invalid", secret="s" * 32, transport=transport)
    assert len(sent) == 1
    assert any(link["event_rate"] is None for link in sent[0]["links"])


def test_push_does_not_swallow_other_failures(tmp_path):
    """Mutation: retry on any HTTPError. A 401 or a 500 is not a schema problem,
    and quietly re-sending would hide a broken ingest behind a second attempt."""
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)

    def transport(_payload, **_kwargs):
        raise _http_error(401)

    with pytest.raises(urllib.error.HTTPError):
        push(snapshot, endpoint="https://ingest.invalid", secret="s" * 32, transport=transport)


def test_push_does_not_retry_any_422(tmp_path):
    snapshot = build_snapshot(_sources(tmp_path), now=NOW)
    for link in snapshot["links"]:
        link["event_rate"] = 1.0
    calls = 0

    def transport(_payload, **_kwargs):
        nonlocal calls
        calls += 1
        raise _http_error(422)

    with pytest.raises(urllib.error.HTTPError):
        push(snapshot, endpoint="https://ingest.invalid", secret="s" * 32, transport=transport)
    assert calls == 1


# -------------------------------------------------------------- Windows links


def _windows_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    worker = tmp_path / "agent-worker"
    telegram = tmp_path / "telegram-bot"
    home.mkdir()
    (worker / "queue").mkdir(parents=True)
    (worker / "done").mkdir()
    telegram.mkdir()

    local_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(NOW - 30))
    _write(
        worker / "heartbeat.json",
        {"ts": local_stamp, "state": "working", "release": "test", "model": "gpu"},
    )
    _write(worker / "metrics.json", {"tasks": 2, "pass": 2, "fail": 0})
    (telegram / "bot.log").write_text(
        f"{local_stamp} alive pid=42 offset=1 pending=0 armed=halted\n",
        encoding="utf-8",
    )
    return home, worker, telegram


def _stub_windows_hardware(monkeypatch) -> None:
    monkeypatch.setattr(
        win_collector,
        "_ollama_ps",
        lambda _url: {
            "ok": True,
            "models": [],
            "loaded_count": 0,
            "vram_bytes": 0,
            "latency_ms": 7.25,
        },
    )
    monkeypatch.setattr(win_collector, "_ollama_tags", lambda _url: {"ok": True, "count": 0})
    monkeypatch.setattr(
        win_collector,
        "_nvidia_smi",
        lambda: {
            "ok": True,
            "gpu_util_pct": 0.0,
            "mem_util_pct": 0.0,
            "mem_used_mib": 0.0,
            "mem_total_mib": 16_000.0,
            "temp_c": 30.0,
            "name": "test GPU",
        },
    )
    monkeypatch.setattr(win_collector, "_disk_free_gb", lambda: 100.0)
    monkeypatch.setattr(win_collector, "_pause_present", lambda _home: False)


def test_windows_links_publish_only_observed_values(tmp_path, monkeypatch):
    home, worker, telegram = _windows_sources(tmp_path)
    _stub_windows_hardware(monkeypatch)

    queued = worker / "queue" / "telegram-task.md"
    queued.write_text(
        "repo: demo\n---\nverify\n\n(queued from Telegram by Ari)\n",
        encoding="utf-8",
    )
    completed = worker / "done" / "other-task.md"
    completed.write_text("repo: demo\n---\nnot from Telegram\n", encoding="utf-8")
    import os

    os.utime(queued, (NOW - 60, NOW - 60))
    os.utime(completed, (NOW - 30, NOW - 30))

    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )
    links = _links(snapshot)

    handoff = links[("telegram-bot", "agent-worker")]
    assert handoff["event_rate"] == 0.2
    assert handoff["latency_ms"] is None

    inference = links[("agent-worker", "ollama-inference")]
    assert inference["latency_ms"] == 7.25
    assert inference["event_rate"] is None

    gpu = links[("ollama-inference", "win-workhorse")]
    assert gpu["latency_ms"] is None
    assert gpu["event_rate"] is None

    archive = links[("agent-worker", "knowledge-archive")]
    assert archive["latency_ms"] is None
    assert archive["event_rate"] == 0.2


def test_windows_alive_heartbeat_is_not_worker_handoff_traffic(tmp_path, monkeypatch):
    home, worker, telegram = _windows_sources(tmp_path)
    _stub_windows_hardware(monkeypatch)
    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )
    assert _links(snapshot)[("telegram-bot", "agent-worker")]["event_rate"] == 0.0


def test_windows_summary_attention_uses_authoritative_pending_review(
    tmp_path, monkeypatch
):
    home, worker, telegram = _windows_sources(tmp_path)
    _stub_windows_hardware(monkeypatch)
    _write(
        telegram / "desk-summary.json",
        {
            "version": 1,
            "updated_at": "2026-07-26T08:00:00+00:00",
            "posture": "capital_preservation",
            "leader": "none",
            "validation": {"oos_pass": 0, "oos_total": 7, "conflicts": 1},
            "decisions": {
                "pending": 2,
                "pending_review": 2,
                "approved_awaiting_execution": 14,
                "eligible_execution": 0,
                "blocked": 14,
            },
            "execution": "halted",
            "feeds": {"fresh": 7, "total": 7},
        },
    )

    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )

    assert snapshot["summary"]["attention"] == 2


def test_missing_windows_measurement_sources_publish_null(tmp_path, monkeypatch):
    home, worker, telegram = _windows_sources(tmp_path)
    _stub_windows_hardware(monkeypatch)
    # Queue alone is only half the append-only stream: a task may already have
    # moved to done. A partial source must not publish a measured zero.
    (worker / "done").rmdir()

    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )
    links = _links(snapshot)
    assert links[("telegram-bot", "agent-worker")]["event_rate"] is None
    assert links[("agent-worker", "knowledge-archive")]["event_rate"] is None


def test_missing_windows_counts_are_described_as_unknown(tmp_path, monkeypatch):
    home, worker, telegram = _windows_sources(tmp_path)
    _write(worker / "metrics.json", {})
    _stub_windows_hardware(monkeypatch)
    monkeypatch.setattr(
        win_collector,
        "_ollama_tags",
        lambda _url: {"ok": False, "count": None},
    )
    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )
    agents = {agent["id"]: agent for agent in snapshot["agents"]}
    assert "task count not observed" in agents["agent-worker"]["activity"]
    assert "available model count not observed" in agents["ollama-inference-host"]["activity"]
    assert "0 tasks" not in agents["agent-worker"]["activity"]


def test_windows_push_never_retries_unknown_rates_as_zero(tmp_path, monkeypatch):
    home, worker, telegram = _windows_sources(tmp_path)
    _stub_windows_hardware(monkeypatch)
    snapshot = win_collector.build_snapshot(
        home,
        agent_worker_dir=worker,
        telegram_bot_dir=telegram,
        now=NOW,
    )
    sent: list[dict] = []

    def transport(payload, **_kwargs):
        sent.append(payload)
        raise _http_error(422)

    with pytest.raises(urllib.error.HTTPError):
        win_collector.push(
            snapshot,
            endpoint="https://ingest.invalid",
            secret="s" * 32,
            transport=transport,
        )
    assert len(sent) == 1
    assert any(link["event_rate"] is None for link in sent[0]["links"])


def test_merged_collector_quarantines_old_windows_proxy_rates(tmp_path):
    mac = build_snapshot(_sources(tmp_path), now=NOW, link_latencies={})
    win = {
        "version": 1,
        "observed_at": _iso(NOW),
        "sequence": 44,
        "summary": {
            "state": "observing",
            "active_agents": 1,
            "events_per_min": 611.0,
            "verified_today": 11,
            "attention": 3,
        },
        "nodes": [
            {
                "id": "win-workhorse",
                "zone": "compute",
                "label": "Windows workhorse",
                "status": "healthy",
                "load_band": "medium",
                "activity_rate": 42.0,
                "freshness_s": 1.0,
            },
            {
                "id": "ollama-inference",
                "zone": "compute",
                "label": "Ollama inference",
                "status": "healthy",
                "load_band": "medium",
                "activity_rate": 8.0,
                "freshness_s": 1.0,
            },
        ],
        "links": [
            {
                "source": "ollama-inference",
                "target": "win-workhorse",
                "status": "healthy",
                "latency_ms": 7.25,
                "event_rate": 42.0,
                "signal_class": "network",
            }
        ],
        "agents": [
            {
                "id": "worker",
                "role": "Agent worker",
                "state": "working",
                "activity": "Worker state observed",
                "verification": "verified",
                "provider_class": "local GPU",
                "updated_at": _iso(NOW),
            }
        ],
        "markets": {
            "network": "Windows workhorse",
            "status": "offline",
            "feed_age_s": 1.0,
            "events_per_min": 42.0,
            "paper_strategies": 7,
            "decision_gate": "off",
            "execution": "off",
        },
        "events": [],
    }

    merged = merged_collector._merge_snapshots(mac, win)
    win_nodes = [node for node in merged["nodes"] if node["id"].startswith(("win-", "ollama-"))]
    win_links = [
        link
        for link in merged["links"]
        if link["source"] == "ollama-inference"
    ]
    assert win_nodes and all(node["activity_rate"] is None for node in win_nodes)
    assert win_links[0]["event_rate"] is None
    assert win_links[0]["latency_ms"] == 7.25
    assert merged["summary"]["events_per_min"] is None
    assert merged["summary"]["verified_today"] is None
    assert merged["summary"]["attention"] is None


def test_merged_collector_sanitizes_remote_personal_text(tmp_path):
    mac = build_snapshot(_sources(tmp_path), now=NOW, link_latencies={})
    win = {
        "version": 1,
        "observed_at": _iso(NOW),
        "sequence": 45,
        "summary": {
            "state": "observing",
            "active_agents": 1,
            "events_per_min": None,
            "verified_today": None,
            "attention": None,
        },
        "nodes": [],
        "links": [],
        "agents": [
            {
                "id": "personal-role",
                "role": "owner@example.com",
                "state": "working",
                "activity": "Call 303-555-0199",
                "verification": "pending",
                "provider_class": "local CPU",
                "updated_at": _iso(NOW),
            }
        ],
        "markets": {},
        "events": [
            {
                "id": "event",
                "observed_at": _iso(NOW),
                "event_class": "agent",
                "source": "intelligence",
                "target": "archive",
                "label": "Ask @private_handle",
                "status": "observed",
            }
        ],
    }
    merged = merged_collector._merge_snapshots(mac, win)
    body = json.dumps(merged)
    assert "owner@example.com" not in body
    assert "303-555-0199" not in body
    assert "@private_handle" not in body
    assert "windows-agent-1" in body


# --------------------------------------------------------- merged degradation


def test_merged_collector_falls_back_to_mac_when_windows_ssh_fails(
    tmp_path, monkeypatch, capsys
):
    mac = build_snapshot(_sources(tmp_path), now=NOW, link_latencies={})
    monkeypatch.setattr(merged_collector.MacSources, "defaults", lambda: object())
    monkeypatch.setattr(
        merged_collector,
        "build_mac_snapshot",
        lambda _sources, **_kwargs: mac,
    )
    monkeypatch.setattr(merged_collector, "mac_configured_latencies", lambda: {})

    def windows_asleep():
        raise RuntimeError("ssh timed out")

    monkeypatch.setattr(merged_collector, "_ssh_win_snapshot", windows_asleep)
    monkeypatch.setattr(
        "sys.argv",
        ["merged_collector.py", "--validate-only", "--compact"],
    )

    assert merged_collector.main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == mac
    assert "publishing Mac-only" in captured.err
def test_windows_collector_reads_only_bounded_desk_projection(tmp_path):
    path = tmp_path / "desk-summary.json"
    expected = {
        "version": 1,
        "updated_at": "2026-07-26T08:00:00+00:00",
        "posture": "capital_preservation",
        "leader": "none",
        "validation": {"oos_pass": 0, "oos_total": 7, "conflicts": 1},
        "decisions": {
            "pending": 1,
            "pending_review": 0,
            "pending_policy_blocked": 1,
            "approved_awaiting_execution": 14,
            "eligible_execution": 0,
            "blocked": 14,
        },
        "execution": "halted",
        "feeds": {"fresh": 7, "total": 7},
        "risk": {
            "ledger_state": "reconciled",
            "realized_drawdown_pct": 24.0,
            "drawdown_limit_pct": 25.0,
            "budget_remaining_pct": 4.0,
            "new_risk": "restricted",
        },
        "experiment": {
            "status": "collecting",
            "qualified_days": 1,
            "required_days": 14,
            "last_committed_date": "2026-07-25",
            "collector": "current",
        },
    }
    path.write_text(json.dumps(expected), encoding="utf-8")
    assert win_collector._desk_projection(path) == expected

    legacy = dict(expected)
    legacy.pop("risk")
    legacy.pop("experiment")
    legacy["decisions"] = {"pending": 0}
    path.write_text(json.dumps(legacy), encoding="utf-8")
    assert win_collector._desk_projection(path)["decisions"] == {
        "pending": 0,
        "pending_review": None,
        "approved_awaiting_execution": None,
        "eligible_execution": None,
        "blocked": None,
        "pending_policy_blocked": None,
    }
    assert win_collector._desk_projection(path)["risk"]["ledger_state"] == "unknown"

    contradictory = dict(expected)
    contradictory["decisions"] = dict(expected["decisions"], blocked=13)
    path.write_text(json.dumps(contradictory), encoding="utf-8")
    assert win_collector._desk_projection(path)["posture"] == "unknown"

    expected["source"] = "private analyst"
    path.write_text(json.dumps(expected), encoding="utf-8")
    assert win_collector._desk_projection(path)["posture"] == "unknown"

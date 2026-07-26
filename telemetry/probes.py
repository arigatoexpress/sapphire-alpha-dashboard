"""Measurement primitives for link telemetry.

Every number this module returns is something that was actually observed. The
rules it exists to enforce:

1. A number in `latency_ms` or `event_rate` is a claim that we measured it. When
   a quantity was not measured the answer is `None`, and `None` is never quietly
   replaced by a default, an estimate, an interpolation, or a plausible-looking
   constant. On a site whose whole pitch is verifiable transparency, an invented
   34 ms is worse than an admitted blank.

2. Absence of entries in an **append-only** source is itself a measurement. A log
   we can read that has nothing inside the window genuinely observed zero events,
   so `0.0` is the honest answer there — not `None`.

3. Absence of freshness in a **state snapshot** is not a measurement. A file that
   reports a value as of a timestamp older than the measurement window cannot
   speak for the window, so its rate is `None` however recently we read it.

Nothing here touches the network at import time and every I/O boundary is an
injectable argument, so the tests measure the logic instead of the house wifi.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


# Long enough that a per-minute rate is not dominated by one stray entry, short
# enough that "right now" still means right now.
DEFAULT_WINDOW_SECONDS = 300.0

_USER_AGENT = {"User-Agent": "sapphire-telemetry/1"}


def http_latency_ms(
    url: str,
    *,
    timeout: float = 2.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    clock: Callable[[], float] = time.perf_counter,
) -> float | None:
    """Round-trip time to one endpoint, or None if the probe did not complete.

    A failed probe is not a slow probe: any error returns None rather than the
    timeout value, because "we could not reach it" and "it took 2000 ms" are
    different facts and only one of them is true.
    """
    if not url:
        return None
    started = clock()
    try:
        request = urllib.request.Request(url, headers=dict(_USER_AGENT))
        with opener(request, timeout=timeout) as response:
            response.read(1)
    except Exception:
        return None
    return round(max(0.0, clock() - started) * 1000, 3)


def _fetch_json(
    url: str,
    *,
    timeout: float,
    opener: Callable[..., Any],
) -> Any:
    request = urllib.request.Request(url, headers=dict(_USER_AGENT))
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def gateway_route_latency_ms(
    health_url: str,
    *,
    timeout: float = 2.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    clock: Callable[[], float] = time.perf_counter,
) -> float | None:
    """RTT to the compute tier the GPU gateway would currently route to.

    The gateway publishes its tiers at `/healthz` and selects the first healthy
    one in configured order, so timing that same tier measures the network leg a
    real inference request pays — not the gateway's own bookkeeping. Reading the
    tier address at runtime also keeps every host address out of this repo.

    None when the gateway is unreachable or reports no healthy tier: with nothing
    routable there is no latency to report, and reporting the local fallback's
    number as the GPU's would be a fabrication.
    """
    if not health_url:
        return None
    try:
        payload = _fetch_json(health_url, timeout=timeout, opener=opener)
    except Exception:
        return None
    tiers = payload.get("tiers") if isinstance(payload, dict) else None
    if not isinstance(tiers, list):
        return None
    for tier in tiers:
        if not isinstance(tier, dict) or not tier.get("healthy"):
            continue
        url = tier.get("url")
        if isinstance(url, str) and url:
            return http_latency_ms(url, timeout=timeout, opener=opener, clock=clock)
    return None


def read_tail_lines(path: Path | str, *, max_bytes: int = 64 * 1024) -> list[str] | None:
    """Last `max_bytes` of a log as lines, or None when it cannot be read.

    None is reserved for "there is no source here". An empty list means the
    source exists and is empty, which is a measurement.
    """
    try:
        target = Path(path)
        size = target.stat().st_size
        with target.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()  # discard the partial first line
            data = handle.read()
    except OSError:
        return None
    return data.decode("utf-8", errors="replace").splitlines()


def log_rate_per_min(
    lines: Iterable[str] | None,
    *,
    now: float,
    parse_ts: Callable[[str], float | None],
    window_s: float = DEFAULT_WINDOW_SECONDS,
) -> float | None:
    """Events per minute from an append-only source over the trailing window.

    Zero is a real answer here: the log is readable and nothing was appended, so
    nothing happened. None means the source itself is missing.
    """
    if lines is None or window_s <= 0:
        return None
    floor = now - window_s
    observed = 0
    for line in lines:
        stamp = parse_ts(line)
        if stamp is not None and floor <= stamp <= now:
            observed += 1
    return round(observed / (window_s / 60.0), 3)


def timestamp_rate_per_min(
    timestamps: Sequence[float] | None,
    *,
    now: float,
    window_s: float = DEFAULT_WINDOW_SECONDS,
) -> float | None:
    """`log_rate_per_min` for a source that already parses to epoch seconds."""
    if timestamps is None or window_s <= 0:
        return None
    floor = now - window_s
    observed = sum(1 for stamp in timestamps if floor <= stamp <= now)
    return round(observed / (window_s / 60.0), 3)


def directory_event_rate_per_min(
    path: Path | str,
    *,
    now: float,
    window_s: float = DEFAULT_WINDOW_SECONDS,
    lister: Callable[[Path], Iterable[Any]] | None = None,
) -> float | None:
    """Completions per minute, counted as files that landed inside the window.

    A directory that things get dropped into is an append-only source, so an
    empty window is a measured zero. None only when the directory is absent.
    """
    target = Path(path)
    listing = lister or (lambda directory: directory.iterdir())
    try:
        entries = list(listing(target))
    except OSError:
        return None
    floor = now - window_s
    observed = 0
    for entry in entries:
        try:
            modified = Path(entry).stat().st_mtime
        except OSError:
            continue
        if floor <= modified <= now:
            observed += 1
    return round(observed / (window_s / 60.0), 3)


def snapshot_measurement(
    value: Any,
    *,
    source_age_s: float,
    window_s: float = DEFAULT_WINDOW_SECONDS,
) -> float | None:
    """A state file's number, but only while that file can still speak for now.

    A snapshot reports what was true when it was written. Once it is older than
    the window, serving its number as the current one is an extrapolation, and
    extrapolations are exactly what this module refuses to make. Returns None.
    """
    if value is None or source_age_s > window_s:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return round(number, 3)

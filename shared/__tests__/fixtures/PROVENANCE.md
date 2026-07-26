# Fixture provenance

## `live-snapshot.json`

A sanitized historical `/api/v1/live` snapshot based on a real producer capture
from 2026-07-25.

Anonymous `GET https://sapphirealpha.xyz/api/v1/live` could not be used directly: at capture
time the public tier was still redacted (`live_telemetry.public_projection` replaces every
number with an adjective), and there is no anonymous route to the un-redacted shape until W2
lands. So the snapshot was captured one step upstream, from the producer that feeds that
endpoint:

```bash
PYTHONPATH=telemetry:backend:. backend/.venv/bin/python telemetry/merged_collector.py \
  | backend/.venv/bin/python -c \
    'import json,sys; sys.path.insert(0,"backend"); import live_telemetry; \
     print(json.dumps(live_telemetry.validate_snapshot(json.load(sys.stdin)), indent=2))'
```

`merged_collector.py` runs the Mac collector plus the Windows collector over SSH — the same
pair prod ingests from. The output was then passed through `live_telemetry.validate_snapshot()`,
the function that defines the stored shape, and the serving fields `get()` appends were added.

The topology remains the captured topology: the same 11 node ids, zones and labels, and the
same 9 links. It is not presented as a fresh live observation.

The old producer used numeric proxies that looked like measurements: model/head counts
multiplied by constants, cumulative task totals labeled as per-minute activity, a stale batch
rate repeated as current, and a hard-coded paper-strategy count. Those values were deliberately
removed during the telemetry-honesty migration:

- all unversioned Windows `activity_rate` and `event_rate` values are `null`;
- Mac rates without an actual current event source are `null`;
- the two retained rates (`0.0` agent events and `599.0` market messages) came from complete,
  append-only/current sources in the captured payload;
- fleet-wide event, verification, and attention counts are `null`;
- `active_agents` is derived from the agents actually present in this fixture; and
- `paper_strategies` is `null` because the captured value came from a constant.

Every retained numeric value therefore has a measurement source; every removed proxy is an
explicit `null`, never a replacement zero.

`validate_snapshot()` runs `_scan_forbidden()` over the whole payload, so this file provably
contains no hostname, URL, IP address, filesystem path or wallet address.

The consumer shape was regenerated the same day against commit `bf76b82`, which renamed the served node field
`load_band` to `load`. Producers still send `load_band` on the wire and the backend renames it
on ingest, so the fixture is what a *consumer* sees, which is what these tests are about.

## `empty-snapshot.json`

The literal output of `live_telemetry._empty_snapshot(public=False, status="offline")` — what
the endpoint serves before any snapshot has been ingested. Note `summary.state` is
`"not observed"`, which is not a member of the ingest enum `_SUMMARY_STATES`; that asymmetry is
real and the shared types model it.

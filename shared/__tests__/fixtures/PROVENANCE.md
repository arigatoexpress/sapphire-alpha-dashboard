# Fixture provenance

## `live-snapshot.json`

A **real** un-redacted `/api/v1/live` snapshot, captured 2026-07-25.

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
the function that defines the stored shape, and the four serving fields `get()` appends
(`status`, `freshness_s`, `served_at`, `received_at`) were added.

Verified against the live endpoint: the topology is identical to what prod was serving at the
same moment — the same 11 node ids, zones and labels, and the same 9 links. Only the redacted
numeric fields differ, which is the entire point of the fixture.

`validate_snapshot()` runs `_scan_forbidden()` over the whole payload, so this file provably
contains no hostname, URL, IP address, filesystem path or wallet address.

Regenerated the same day against commit `bf76b82`, which renamed the served node field
`load_band` to `load`. Producers still send `load_band` on the wire and the backend renames it
on ingest, so the fixture is what a *consumer* sees, which is what these tests are about.

## `empty-snapshot.json`

The literal output of `live_telemetry._empty_snapshot(public=False, status="offline")` — what
the endpoint serves before any snapshot has been ingested. Note `summary.state` is
`"not observed"`, which is not a member of the ingest enum `_SUMMARY_STATES`; that asymmetry is
real and the shared types model it.

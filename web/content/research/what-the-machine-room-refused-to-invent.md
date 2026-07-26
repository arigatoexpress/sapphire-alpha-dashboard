---
title: What the Machine Room refused to invent
description: A measurement audit of the public system map, the telemetry claims it could support, and the gaps it now leaves visible.
date: 2026-07-25
tags: [engineering, telemetry, audit]
publish: true
---

A live architecture can be more misleading than a static diagram. Motion implies activity. A millisecond label implies a clock. A red mark implies a failed service. If those implications cannot be traced to an observation, the display is theatre with a timestamp.

This audit asked a narrower question than “does the dashboard look live?”:

> For every value and every animation in the Machine Room, what was actually measured?

The answer changed the product. Missing measurements now remain missing, categorical reports never become numerical animation, and an old report stops speaking in the present tense.

## Scope and method

The audit followed one captured public snapshot through the code that produced, validated, served, and narrated it. The evidence set was:

- the declared eleven-part, nine-connection architecture;
- the captured live-schema fixture used by the shared contract tests;
- the Mac, Windows, and merged telemetry collectors;
- the live-telemetry validator and serving layer;
- the publisher schedule and staleness threshold;
- the view-model code that turns fields into prose and motion.

The relevant repository paths are `telemetry/collector.py`, `telemetry/win_collector.py`, `telemetry/merged_collector.py`, `backend/live_telemetry.py`, `shared/telemetry.ts`, `shared/narrate.ts`, and `shared/__tests__/fixtures/live-snapshot.json`.

This was a code-and-fixture audit, not a load test or an uptime study. It can establish how a displayed claim was constructed. It cannot establish end-to-end latency or historical availability where no instrument recorded those things.

## Finding 1: absence was being handled honestly, but not explained

All nine declared connections in the captured snapshot carried `latency_ms: null`. The collector populates those values only when explicit link probes are configured, and no such probe configuration was present during the audit.

The correct result is not zero milliseconds, a midpoint inferred from a band, or a visually pleasing placeholder. It is **not measured**.

That distinction matters because zero and missing are different facts:

- `0` means an instrument ran and observed none.
- `null` means no usable reading exists.

The Machine Room now carries that difference into both its visual and text views. A missing value has no digit, and a measured zero remains a real reading.

## Finding 2: several “rates” were counts wearing a time unit

A rate promises a numerator and a time window. At audit time, only the market-message source was derived from messages observed per minute. Other activity fields were constructed from service counts, agent counts, queue depth, model availability, insert totals divided by a constant, or cumulative task totals.

Those inputs can be useful operational signals. They are not events per minute merely because the output field has that name.

| Display claim | Audit evidence | Safe conclusion |
|---|---|---|
| Link latency | Nine null values; probe inputs absent | Show no timing |
| Market message rate | Recent messages counted over a minute | Eligible to drive a rate display |
| Service or agent activity | Counts multiplied by fixed constants | Categorical load at most, not a measured rate |
| Archive activity | Insert total divided by a constant | Throughput not established without an observed interval |
| Cumulative task count | Lifetime total placed in a rate field | Count only; must not drive speed |

The lesson is dimensional, not cosmetic: renaming a count does not create a clock.

## Finding 3: health depends on cadence and semantics

Two red states had different causes from the failure a visitor would reasonably infer.

One scheduled workflow ran on a six-hour cadence but was judged against a fifteen-minute freshness threshold. It was therefore capable of appearing failed for most of its normal interval. Separately, an intelligence status treated the absence of a recent event as “down,” even when the system was simply idle.

A useful health check has to ask the right question:

- For a scheduled job: did it complete within its promised cadence?
- For an event-driven worker: is it able to accept work?
- For a stream: did expected data stop arriving?

“Nothing happened recently” is not one universal failure condition.

## Finding 4: optional infrastructure was not isolated

The merged publisher was described as able to continue with the local half of the system when the secondary machine was unavailable. The audited error path did not uphold that promise: the unavailable branch could stop the combined publication instead of emitting a partial, explicitly degraded report.

That is a reliability issue and a truthfulness issue. If a component is optional, its loss should reduce the report’s coverage, not silently prevent every other healthy component from reporting.

## Product rules that followed

The public view now uses four rules that are testable rather than stylistic:

1. **Only a complete exact-schema response can expose numeric rates.** A partial migration is downgraded.
2. **Legacy bands remain bands.** Words such as “busy” or “under 20 ms” are never inverted into values.
3. **Motion requires an exact positive rate.** Exact zero is still; no exact rate is dotted and still.
4. **Time keeps passing in the browser.** A report ages into stale state, and an unreachable feed leaves the last report visible as history rather than describing it as now.

These rules also govern the no-JavaScript page. Before a valid response arrives, the architecture remains readable, but every live figure is explicitly absent.

## What would prove the repair

The visual policy is now covered by golden tests, but the measurement system needs its own continuing evidence:

- fake-clock tests that relate every health threshold to the producer’s real cadence;
- collector tests that reject counts placed in rate fields;
- probe tests that distinguish unavailable timing from measured zero;
- a secondary-machine-offline test that still publishes the local snapshot;
- compatibility tests against both the previous banded response and the exact response;
- a mutation test showing that removing the precision check causes the suite to fail.

Until those producer checks are green in the deployed path, the defensible claim is modest: the page will show what the feed supplies, and it will make the missing parts visible. It does not claim latency, throughput, or uptime that no instrument has measured.

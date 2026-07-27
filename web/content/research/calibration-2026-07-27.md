---
title: Learning loop — wins, losses, calibration
description: Scheduled scoring of event probabilities and path forecasts. Brier calibration, lessons, and prior updates for the self-improving desk.
date: 2026-07-27
tags: [calibration, learning, conjecture, post-mortem, methodology]
publish: true
---

# Learning loop — 2026-07-27

The desk does not only publish opinions. On a schedule it **scores** them, **records wins and losses**, **updates priors**, and **writes notes** so the next cycle is smarter than the last. This is the public face of that loop.

> Not investment advice. Designated test/agentic capital only.

## Cadence

| Interval | What happens |
| --- | --- |
| **Every conjecture cycle** | Open book refreshed; due events scored; priors reloaded |
| **Daily** | Full learning cycle: score → calibrate → learn → publish this report |
| **Weekly** | Domain roll-up, lesson pruning, path-band hit-rate review |
| **At resolution window** | Each event gets a binary outcome + Brier score |

## Snapshot

- Open event opinions: **12**
- Resolved (scored): **0**
- Expired (no hard resolve): **0**
- Path forecasts scored: **0**
- Mean Brier: **—** (0 perfect · ~0.25 coin-flip)
- Lean accuracy: **—**
- Skill vs coin-flip: **—**

## Prior updates feeding the next cycle

Global bias pull: **-0.0** (n=0, mean error=0.0).

No resolved events yet — priors stay at system defaults until the first resolution windows close. Open opinions are still tracked and will score on schedule.

## What this enables

1. **Accountability** — every published P can be wrong in public.
2. **Self-correction** — chronic overconfidence shrinks automatically.
3. **Domain skill map** — know where the desk has edge vs noise.
4. **Agent notes** — losses become instructions, not forgotten chat.
5. **Money loop** — trade outcomes (when ledger-joined) feed size discipline.

This runs on open market data, open-source tooling, and local models where possible. It is built to evolve continuously — not as a static blog.

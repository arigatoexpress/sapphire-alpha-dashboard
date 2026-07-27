---
title: How we form market opinions
description: >
  Event probabilities as of now, path forecasts for targets and trends, public data
  sources, falsifiers, and how speculation is kept honest.
date: 2026-07-27
tags: [methodology, conjecture, research]
publish: true
---

# How we form market opinions

This is the public research contract for Sapphire Alpha.

## What we are doing

We run a **research and conjecture engine** on public market data, then publish:

1. **Event probabilities** — one number *as of a timestamp* for binary claims  
   (e.g. “Has Bitcoin put in the cycle low?”).
2. **Path forecasts** — short / medium / long **price and trend bands**, not event odds.
3. **Falsifiers** — written before the outcome so we can score accuracy later.
4. **Trade ideas** — gated thesis-lane notions only; not auto-advice for outside capital.

We allow the system to **speculate**, including on ambiguous regimes. Speculation is
labeled and forced to cite data and a falsifier. It is not free narrative.

## What we are not doing

- Multi-horizon probabilities for the same binary event (that confuses readers).
- Point-price “targets” without scenarios.
- Publishing live balances, wallets, or private holdings.
- Guaranteeing returns.

## Data

Baseline loop uses free public feeds:

| Source | Use |
| --- | --- |
| CoinGecko | BTC/ETH/SOL spot, 24h/7d/30d changes |
| CoinGecko global | BTC dominance, total mcap |
| Yahoo chart (best-effort) | VIX, SPX, DXY, oil, gold proxies |

Each opinion carries a **data_quality** score (0–1) from feed coverage. Low quality
means higher prior weight — treat those opinions as softer.

## Method in one loop

```
public market snapshot
        ↓
event probabilities (single p) + path bands (S/M/L)
        ↓
falsifiers + evidence bullets
        ↓
trade ideas (gated) + portfolio multi-lens
        ↓
publish markdown · later Brier-style scoring
```

## Confidence labels

Each opinion also carries a **confidence** label (separate from the probability):

| Label | Meaning |
| --- | --- |
| `moderate` | Strong data coverage and a clear lean |
| `tentative` | Usable data, modest lean |
| `low` | Thin edge or incomplete feeds |
| `speculative` | Prior-heavy; treat as hypothesis, not conviction |

We still **conjecture** under thin data — markets require it — but we label it so readers
can size skepticism correctly.

## Why this is useful

- **Comparable over time** — one P per event, not three overlapping odds.
- **Honest about uncertainty** — residual mass (1 − p) is explicit in every book row.
- **Learnable** — falsifiers and resolution windows make calibration possible.
- **Separates thesis from path** — “is the low in?” vs “where might price go in 90 days?”
- **Data-weighted** — thin feeds shrink extremity toward the prior.

## Process

1. Observe — public market snapshot.  
2. Conjecture — one probability per binary event, with drivers + data quality.  
3. Path forecast — short/med/long bands for prices and trends only.  
4. Score — resolve at the written window (Brier-style).  
5. Act (gated) — designated rails under caps only.

Not investment advice. Designated test/agentic capital only.

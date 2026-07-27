---
title: How we form market opinions
description: >
  Event probabilities as of now, path forecasts for targets and trends, public data,
  falsifiers, and a scheduled self-improving learning loop that scores wins and losses.
date: 2026-07-27
tags: [methodology, conjecture, research, learning, calibration]
publish: true
---

# How we form market opinions

This is the public research contract for Sapphire Alpha — and the charter for a
**self-improving local agentic system** that observes markets, publishes opinions,
scores itself, and updates its own priors.

## What we are doing

1. **Event probabilities** — one number *as of a timestamp* for binary claims  
   (e.g. “Has Bitcoin put in the cycle low?”).
2. **Path forecasts** — short / medium / long **price and trend bands**, not event odds.
3. **Falsifiers** — written before the outcome so we can score accuracy later.
4. **Learning loop** — on a schedule we resolve due claims, compute Brier scores,
   record wins/losses, update priors, and publish calibration notes.
5. **Trade ideas** — gated thesis-lane notions on designated capital only.

We allow the system to **speculate**, including on ambiguous regimes. Speculation is
labeled and forced to cite data and a falsifier. After the fact, it is **scored**.

## What we are not doing

- Multi-horizon probabilities for the same binary event.
- Point-price “targets” without scenarios.
- Publishing live balances, wallets, or private holdings.
- Guaranteeing returns or claiming permanent edge.
- Paper backtest leaderboards as “research.”

## Data

| Source | Use |
| --- | --- |
| CoinGecko | BTC/ETH/SOL spot, 24h/7d/30d changes |
| CoinGecko global | BTC dominance, total mcap |
| Yahoo chart (best-effort) | VIX, SPX, DXY, oil, gold proxies |
| Local learning store | resolved outcomes, prior deltas, lessons |

Each opinion carries a **data_quality** score (0–1). Low quality → more prior weight.

## Method — full autonomous loop

```
public market snapshot
        ↓
event probabilities (single p) + path bands (S/M/L)
   ↑ prior Δ from past scores
        ↓
falsifiers + drivers + confidence labels
        ↓
open book (track) + trade ideas (gated)
        ↓
score due events (Brier) + path hit-rate
        ↓
learn: update priors · write lessons · note-taking
        ↓
publish opinions + calibration report
        ↓
(act on designated rails under caps — 24/7 when armed)
```

## Learning cadence

| Interval | What the system does |
| --- | --- |
| **Every cycle** | Refresh open book; score anything past its review window; reload priors |
| **Daily** | Full learning cycle + publish calibration / post-mortem |
| **Weekly** | Domain roll-up, lesson pruning, path-band hit-rate review |
| **At resolution** | Binary outcome + Brier; lean accuracy when stance was lean_yes/no |

### Metrics we track

- **Brier score** — (p − outcome)² · 0 perfect · ~0.25 unskilled 50/50  
- **Lean accuracy** — when we leaned, were we directionally right?  
- **Skill vs coin-flip** — 0.25 − mean Brier (positive = better than noise)  
- **Path hit-rate** — did price land inside the published bear–bull band?  
- **Prior Δ** — automatic cool-down of chronic overconfidence per question  

Wins and losses become **lessons** stored as agent notes. The next opinion cycle
reads those notes as prior adjustments — not as forgotten chat.

## Confidence labels

| Label | Meaning |
| --- | --- |
| `moderate` | Strong data coverage and a clear lean |
| `tentative` | Usable data, modest lean |
| `low` | Thin edge or incomplete feeds |
| `speculative` | Prior-heavy; treat as hypothesis |

## Why this is useful

- **Comparable over time** — one P per event.
- **Honest uncertainty** — residual mass (1 − p) is explicit.
- **Self-correcting** — bad calibration shrinks future extremity.
- **Separates thesis from path** — event vs price trajectory.
- **Built for autonomy** — open data, open-source stack, local models where possible;
  execution stays on designated rails with caps and a kill switch.

## Process claim

1. Observe  
2. Conjecture (single event P + learned prior)  
3. Path forecast (S/M/L only for prices/trends)  
4. Score  
5. Learn + note  
6. Act (gated)

Not investment advice. Designated test/agentic capital only. The goal is a continuously
improving system that earns on those rails — not a static research blog.

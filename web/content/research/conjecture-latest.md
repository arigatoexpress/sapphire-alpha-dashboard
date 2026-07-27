---
title: Market opinions — events and path forecasts
description: Point-in-time event probabilities, short/med/long path forecasts, data quality, drivers, and written falsifiers.
date: 2026-07-27
tags: [conjecture, crypto, macro, commodities, predictions, trade-calls]
publish: false
---

# Market opinions — 2026-07-27

As of this report, with BTC at $64,910, we publish data-backed event probabilities and path forecasts — not guarantees. Average data quality 0.96/1.00. Every claim has a falsifier; execution stays on designated rails under caps and gates.

> Not investment advice. System opinions for designated test/agentic capital only. Past scoring does not guarantee future calibration.

## How to read this report

1. **Data** — public feeds (CoinGecko spot/dominance; Yahoo macro proxies: VIX, SPX, DXY, oil, gold). Missing feeds lower `data_quality` and pull probabilities toward the prior.
2. **Events** — each binary claim gets **one probability as of the timestamp** (e.g. “BTC cycle low is in”). We do **not** assign short/med/long odds to the same event.
3. **Path forecasts** — short / medium / long bands for **prices and trends only**, with bear/base/bull scenarios conditioned on related event probabilities.
4. **Drivers** — the market facts that moved each probability this cycle.
5. **Falsifiers** — written before outcomes so we can score (Brier-style) later.
6. **Speculation** — allowed when the claim is ambiguous; labeled via confidence (`speculative` / `low` / `tentative` / `moderate`) and still forced to cite data.

**Average data quality this cycle:** 0.96 / 1.00

## Market snapshot (public feeds)

| Field | Value |
| --- | --- |
| BTC | $64,910 |
| BTC 24h | +0.50% |
| BTC dominance | 56.5% |
| ETH/BTC | 0.0299 |
| VIX | 18.7 |
| SPX ~3m | +3.2% |
| DXY ~3m | +3.0% |
| Feed mode | live |

## Key takes

- Weakest held vibes: **RCAT** (defensive, bias `trim_or_hedge_cluster`).
- Highest held p_up 90d: **QNT** 54% · hold_study.
- Cluster **crypto_risk_perp** active on book/priority: HYPE, LIT (driver: perp volume + BTC risk appetite). Size as one bet.
- Cluster **ai_narrative** active on book/priority: BOT, PLTR, VVV (driver: AI capex / scarcity premium). Size as one bet.
- Cluster **space** active on book/priority: SPCX, DXYZ, ARKX (driver: SpaceX float + space thematic). Size as one bet.
- Cluster **sound_money** active on book/priority: GLD, IBIT (driver: macro/liquidity/adoption). Size as one bet.
- Critical calendar: **HYPE** 2026-07-28 — unlock_window_primary_trackers.
- Critical calendar: **HYPE** 2026-07-29 — unlock_window_alternate_day.
- Critical calendar: **LIT** 2026-12-27 — INSIDER_CLIFF.
- Trending crypto pulse: PONS, AEON, PENGU.
- — macro context —
- Bitcoin cycle-low (as of now): **51%** probability the low is in (uncertain). Single event P — not short/med/long.
- Four-year cycle map: **63%** useful (not broken). Treat as a prior, not a calendar oracle.
- Structure: BTC.D rising p=58%; alt-season ≤90d p=54%.
- Macro: risk-on 30d p=53%; US recession ≤12m p=28%.

## Has Bitcoin bottomed for this phase?

**Probability (as of 2026-07-27T14:30:53Z): 51%** · stance `uncertain` · confidence `low`.

Single event probability at formation time — **not** short/med/long odds. Review window for scoring: **90 days**.

**Falsifier:** Falsified if BTC makes a fresh cycle low >8% below the price at call time within 90 days, or closes a week >15% below call-time price without reclaiming it in 30d. (Uncertain — small expression only.)

**Drivers this cycle:**
- Drawdown vs ~$109k ATH proxy: 40%
- Desk posture: neutral

**Evidence:**
- Data quality for this claim: 0.96/1.0 (feeds: coingecko, coingecko_global, yahoo_chart)
- Desk posture: neutral
- Drawdown vs ~$109k ATH proxy: 40%
- BTC spot: $64,910
- BTC 24h: +0.5%
- Single event P; path targets are separate (short/med/long bands).

Interpretation: 51% for “yes, the low is in” leaves 49% residual mass that it is not. Price *targets* live in the path-forecast section below.

## Event opinion book (as of now)

| Question | P | Residual | Stance | Conf. | Data Q | Score in |
| --- | --- | --- | --- | --- | --- | --- |
| Bitcoin has put in the cycle low for this bear/corrective phase | 51% | 49% | uncertain | low | 0.96 | 90d |
| The classic ~4-year Bitcoin halving cycle remains a useful regim… | 63% | 37% | lean_yes | tentative | 0.96 | 365d |
| BTC dominance will be higher over the next 90 days (flight-to-qu… | 58% | 42% | uncertain | low | 0.96 | 90d |
| A broad alt-season (majority of large alts outperforming BTC) be… | 54% | 46% | uncertain | low | 0.96 | 90d |
| ETH will outperform BTC on a 90-day total-return basis | 49% | 51% | uncertain | low | 0.96 | 90d |
| Global risk-on continues over the next 30 days (equities bid, cr… | 53% | 47% | uncertain | low | 0.96 | 30d |
| USD strength fades over 90 days (DXY lower), supporting hard ass… | 58% | 42% | uncertain | low | 0.96 | 90d |
| Crude oil remains range-bound (no >20% trend move) over 90 days | 55% | 45% | uncertain | low | 0.96 | 90d |
| Gold is higher over 90 days (real-rate / fiscal dominance bid co… | 49% | 51% | uncertain | low | 0.96 | 90d |
| A multi-year commodity supercycle (energy + metals) remains inta… | 48% | 52% | uncertain | low | 0.96 | 180d |
| The US enters a NBER-style recession within 12 months | 28% | 72% | lean_no | moderate | 0.96 | 365d |
| AI infrastructure / agent-economy equities remain a positive exp… | 58% | 42% | uncertain | low | 0.96 | 180d |

## Structure notes

### Four-year cycle theory

**p = 63%** · residual 37% · stance `lean_yes` · confidence `tentative` · data Q 0.96

The classic ~4-year Bitcoin halving cycle remains a useful regime map (not broken by ETFs/institutions)

- Driver: Cycle-position DD proxy: 40% (mid-bear zone supports map utility)
- Driver: Prior 0.58 — ETF structure can stretch but not erase liquidity seasonality

*Falsifier:* Falsified if post-halving year fails to produce a higher high vs prior cycle peak by +730d from call, *and* BTC underperforms a 60/40 global equity-bond proxy over that window. (Called lean-yes — wrong side hurts more; size accordingly.)

### BTC dominance

**p = 58%** · residual 42% · stance `uncertain` · confidence `low` · data Q 0.96

BTC dominance will be higher over the next 90 days (flight-to-quality / liquidity concentration)

- Driver: BTC.D now: 56.5%
- Driver: SPX ~3m: +3.2% (risk appetite)

*Falsifier:* Falsified if BTC.D is ≥1.5pp lower at +90d without an interim stress spike that fully reverses. (Uncertain — small expression only.)

### Alt coins / alt-season

**p = 54%** · residual 46% · stance `uncertain` · confidence `low` · data Q 0.96

A broad alt-season (majority of large alts outperforming BTC) begins within 90 days

- Driver: BTC.D now: 56.5%
- Driver: SPX ~3m: +3.2% (risk appetite)

*Falsifier:* Falsified if at +90d fewer than 40% of top-20 alts (ex-stables) beat BTC on the window. (Uncertain — small expression only.)

### Macro risk

**p = 53%** · residual 47% · stance `uncertain` · confidence `low` · data Q 0.96

Global risk-on continues over the next 30 days (equities bid, credit stable, vol contained)

- Driver: VIX: 18.7
- Driver: SPX ~3m: +3.2%

*Falsifier:* Falsified if SPX −8% peak-to-trough within 30d or VIX closes above 28 for 3 sessions. (Uncertain — small expression only.)

### US recession

**p = 28%** · residual 72% · stance `lean_no` · confidence `moderate` · data Q 0.96

The US enters a NBER-style recession within 12 months

- Driver: VIX: 18.7
- Driver: SPX ~3m: +3.2%

*Falsifier:* Falsified if no NBER recession is declared/dated within 12 months of call. (Called lean-no — being early on the other side is the main risk.)

### AI infrastructure sleeve

**p = 58%** · residual 42% · stance `uncertain` · confidence `low` · data Q 0.96

AI infrastructure / agent-economy equities remain a positive expected-value sleeve on a 6-month view

- Driver: Risk backdrop SPX ~3m: +3.2%
- Driver: Posture neutral; recession veto softens size not the base prior

*Falsifier:* Falsified if equal-weight AI-infra sleeve −25% vs SPX over 180d with no thesis revision. (Uncertain — small expression only.)

## Path forecasts — price targets by horizon

Short / medium / long here describe **path length** for targets and trend bands, not event odds.

### BTC — short (30d) (spot 64910.0)

| Scenario | Price | Weight |
| --- | --- | --- |
| bear | 57121.0 | 27% |
| base | 66208.0 | 40% |
| bull | 72699.0 | 35% |

_short path band (30d). Conditioned on event p(BTC bottom)=51%; not a multi-horizon event probability._

### BTC — medium (90d) (spot 64910.0)

| Scenario | Price | Weight |
| --- | --- | --- |
| bear | 46735.0 | 27% |
| base | 66620.0 | 40% |
| bull | 86210.0 | 35% |

_medium path band (90d). Conditioned on event p(BTC bottom)=51%; not a multi-horizon event probability._

### BTC — long (365d) (spot 64910.0)

| Scenario | Price | Weight |
| --- | --- | --- |
| bear | 35700.0 | 27% |
| base | 81138.0 | 40% |
| bull | 136311.0 | 35% |

_long path band (365d). Conditioned on event p(BTC bottom)=51%; not a multi-horizon event probability._

### ETH — medium (90d) (spot 1940.08)

| Scenario | Price | Weight |
| --- | --- | --- |
| bear | 1358.0 | 51% |
| base | 2037.0 | 40% |
| bull | 2813.0 | 39% |

_medium path band (90d). Conditioned on event p(ETH>BTC 90d)=49%; not a multi-horizon event probability._

## Trade ideas (gated thesis lane)

### BUY AI_INFRA_SLEEVE

- Thesis: `defense-tech/ai-infra`
- Confidence: 50%
- Path horizon: medium (position hold style, not event P)
- Size tier: dust
- AI infra still investable p=58%; recession 12m p=28%. Keep conviction sleeve; size with recession veto.
- Falsifier: Falsified if equal-weight AI-infra sleeve −25% vs SPX over 180d with no thesis revision. (Uncertain — small expression only.)

### BUY BTC

- Thesis: `sound-money/uncertain-probe`
- Confidence: 41%
- Path horizon: short (position hold style, not event P)
- Size tier: dust
- BTC cycle-low uncertain (p=51%). Dust probe only — scale only if falsifier path fails to trigger and breadth improves.
- Falsifier: Falsified if BTC makes a fresh cycle low >8% below the price at call time within 90 days, or closes a week >15% below call-time price without reclaiming it in 30d. (Uncertain — small expression only.)

## Learning loop — wins, losses, priors

On every cycle we **score due opinions**, **review open paths**, **update priors**, and **write lessons**. Scheduled daily/weekly reports publish the full post-mortem. This is how the desk evolves instead of narrating.

No resolved opinions yet — learning starts after first review horizons.

- Resolved n: **0** (book is open and will score at each review window)
- Prior bias pull this cycle: **-0.0** · lessons: **0**
- Path bands scored: **0** open **4** · hit-rate **None**

See the latest public calibration report: `calibration-YYYY-MM-DD` / `desk-calibration-latest` in research.

## Process

1. **Observe** — public market data.  
2. **Conjecture** — one probability per binary event (+ learned prior Δ).  
3. **Path forecast** — short/med/long bands for prices and trends only.  
4. **Score** — resolve due events (Brier) and path hit-rate.  
5. **Learn** — update priors, write lessons, publish calibration.  
6. **Act (gated)** — designated rails under caps only.

---
title: Robinhood Agentic free-reign — how the desk is allowed to act
description: >
  The public contract for free-reign easy on designated RH Agentic capital:
  clip-to-cap, per-venue slots, Super Heavy as planner only, kill switch always wins.
date: 2026-07-27
tags: [trading, agentic, robinhood, free-reign]
publish: true
---

# Robinhood Agentic free-reign

This note documents the **public** operating contract for Sapphire Alpha’s
designated agentic brokerage rail. It is not a performance claim, not an offer
of managed capital, and not investment advice.

## What free-reign is

Free-reign is a **policy layer**, not a second broker. When all of the following
hold:

1. Gate is **ARMED** (operator arm only)
2. Kill switch is **absent** (unreadable = present)
3. Policy file says **enabled** with mode **easy** (or equivalent auto-approve)

…then qualifying proposals on the **brokerage** venue are auto-approved through
the same decision ledger a human ✅ would use. The executor still enforces caps,
shields, and wallet fences at consume time.

## What free-reign is not

- Not access to client money, production wallets, or non-agentic brokerage accounts
- Not authority for models to hold keys or expand their own caps
- Not a guarantee of fill, edge, or positive expectancy
- Not crypto placement via the Agentic MCP path (crypto is split off by design)

## Lanes

| Lane | Meaning | Sizing |
|------|---------|--------|
| Verified | Systematic track with a fresh passing walk-forward | Larger per-trade cap |
| Thesis | Conviction / news / non-verified track | Smaller per-trade cap |
| L2 easy | Named on-chain tracks on the designated lab wallet only | L2 ticket ceiling |

Oversized tickets **clip to the lane cap** rather than bouncing on a few dollars
of overshoot. Daily notional and **per-venue** position slots still bind.

## Orchestration

**Grok Super Heavy** is the primary plant planner. It may schedule research,
propose, and report — it does **not** place orders. Local Nemotron is the offline
fallback. VPIN, TA alerts, and TradingView webhooks are **advisory inputs** until
they become ledger proposals and pass the gate.

## Failure modes (fail-closed)

| Condition | Result |
|-----------|--------|
| Kill switch present | No execution path |
| Gate disarmed | Free-reign inert |
| Wallet not fenced | Blocked |
| Cap breached after clip | No approve |
| Check unreadable | Treated as fail / halt |

## Public boundary

This site never publishes the live book, exact balances, or current limits.
Architecture telemetry is a separate, capital-free contract.

> Designated test and agentic capital only. Trading risks loss of principal.

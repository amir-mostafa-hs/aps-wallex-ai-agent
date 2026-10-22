# 04: Candidate Screening & Review Priority Queue

**What to build:**
A fast, lightweight scanning engine that periodically (every 15 seconds) evaluates all allowlisted markets on cached features, scores and ranks them without invoking LLMs, filters candidates with poor liquidity or negative edge, and feeds a prioritized review queue where active open positions nearing invalidation or holding limits take strict precedence over new entry candidates.

**Blocked by:**
02: Market Universe Ingestion & Allowlist Filter, 03: Historical Candle Buffer & Feature Engine

**Status:**
resolved

## Acceptance Criteria

- [x] Runs a periodic scan cycle (default 15s) over all eligible allowlisted markets using cached features.
- [x] Computes objective candidate scores based on trend strength, volume expansion, volatility, and execution spread.
- [x] Excludes symbols with insufficient volume, wide spreads, or unverified execution data, logging explicit exclusion reasons.
- [x] Selects the top candidates (default top 3) for detailed AI evaluation.
- [x] Maintains an AI Review Priority Queue that prioritizes open positions nearing stop/time thresholds over new entry candidates.
- [x] Enforces AI call budget (minimum 30 seconds interval, max 3 calls/min).
- [x] Unit tests verify candidate ranking accuracy, priority queue ordering, and scan cycle timing.

# 07: Local Watchdog & Emergency Exit Manager

**What to build:**
A standalone, high-frequency Local Price Watchdog and emergency exit manager that operates independently of the LLM cycle. It continuously tracks real-time market prices, max holding time limits, and invalidation rules for all active positions, deterministically triggering emergency exit orders (closing 100% of the active position) when hard stop-losses or timeout conditions are breached, with full documentation of watchdog operational risks.

**Blocked by:**
01: Project Foundation, Core Types & Config, 06: Deterministic Portfolio Risk Engine & Sizing

**Status:**
resolved

## Acceptance Criteria

- [x] Watchdog runs on an independent loop monitoring live ticks, order book bids, and elapsed holding duration for all open positions.
- [x] Operates with 100% independence from LLM availability: never waits for or requests AI decisions during emergency liquidation.
- [x] Triggers emergency full position close (`EXIT`) when price hits or breaches the hard stop-loss level.
- [x] Triggers emergency exit when position duration exceeds `max_holding_minutes`.
- [x] Enforces cancel-and-replace safety: cancels pending entry orders before triggering exits.
- [x] Logs and monitors local watchdog failure risks (network drops, process crashes, price staleness, exchange order rejection).
- [x] Unit and simulation tests prove stop-loss and time-expiry triggers execute reliably under simulated price spikes and dropped connections.

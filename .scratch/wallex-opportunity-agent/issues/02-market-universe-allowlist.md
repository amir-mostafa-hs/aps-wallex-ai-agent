# 02: Market Universe Ingestion & Allowlist Filter

**What to build:**
An automated market universe manager that ingests active markets from the official Wallex API, unifies the local static denylist (`docs/sources/inactive_markets.json`) with the live package 183 unavailable markets (`unavailableMarkets`), and calculates an immutable Fail-Closed allowlist of tradeable Spot markets with their exact symbol precision attributes (`amount_precision`, `price_precision`).

**Blocked by:**
01: Project Foundation, Core Types & Config

**Status:**
resolved

## Acceptance Criteria

- [x] Ingests all available markets and filters exclusively for active Spot markets (`is_spot: true`).
- [x] Normalizes symbol formats across local and remote sources (removing slashes, converting to uppercase).
- [x] Unions the local denylist with the live package 183 unavailable markets list.
- [x] Produces the tradeable Spot allowlist (matching the verified 120 markets universe).
- [x] Extracts and attaches `amount_precision` (step size) and `price_precision` (tick size) per market.
- [x] Operates Fail-Closed: if denylist or market data is missing or corrupted, the allowlist is empty and live trading is disabled.
- [x] Unit and integration tests verify allowlist computation, symbol normalization, and fail-closed error handling.

# 11: Preflight Safety Gate & Live Trading Enabler

**What to build:**
A comprehensive, automated preflight verification suite that gates activation of `live` trading mode. It verifies API key `TRADE` permissions under the dedicated credit sub-account with `sub-account-client-id`, verifies market allowlist calculation, validates symbol precision and minimum notional thresholds from API, executes non-trading simulation of the local watchdog emergency exit, inspects `expireAt` for credit duration monitoring, and prevents live startup unless all preflight gates pass and explicit confirmation flags are set.

**Blocked by:**
02: Market Universe Ingestion & Allowlist Filter, 07: Local Watchdog & Emergency Exit Manager, 08: Order Executor, Client ID Tracking & Reconciliation, 10: Multi-Mode Engine (Backtest, Shadow & Simulated Replay)

**Status:**
resolved

## Acceptance Criteria

- [x] Automated preflight check validates API key has `TRADE` capabilities on the credit sub-account (`sub-account-client-id`).
- [x] Validates allowlist integrity (denylist present and active Spot universe successfully filtered).
- [x] Queries live API for target market step sizes and minimum notional constraints; excludes any unverified market.
- [x] Verifies local watchdog emergency exit functionality via mock execution.
- [x] Queries `GET /v1/prop/user/packages/active` to determine exact `expireAt` timestamp and timezone; schedules entry cutoff and pre-expiry position liquidation (default 2 hours before expiration).
- [x] Live mode requires `MODE=live`, `LIVE_TRADING_ENABLED=true`, `LIVE_PREFLIGHT_ACKNOWLEDGED=true`, and all automated checks to pass.
- [x] If any preflight check fails, startup halts immediately with clear diagnostic logs; live execution remains strictly locked.
- [x] Unit and mock tests verify that any preflight failure completely blocks live trading.

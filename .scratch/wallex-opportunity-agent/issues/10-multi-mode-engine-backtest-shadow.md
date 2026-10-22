# 10: Multi-Mode Engine (Backtest, Shadow & Simulated Replay)

**What to build:**
The primary system-level testing seam (`SystemTradingHarness`) enabling execution in `backtest`, `shadow`, and `live` modes with 100% semantic parity. In `shadow` mode, the agent ingests live market data and runs real AI decisions and risk evaluations, but executes orders through a simulated exchange adapter modeling realistic fees, slippage, and fills. In `backtest` mode, it replays historical candle data. It also includes an automated end-of-run liquidator that flattens all open positions into TMN before contest/simulation end.

**Blocked by:**
04: Candidate Screening & Review Priority Queue, 05: LangChain Decision Agent & Semantic Validator, 07: Local Watchdog & Emergency Exit Manager, 08: Order Executor, Client ID Tracking & Reconciliation, 09: SQLite WAL Telemetry, Dual P&L & Trade Auditor

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Implements the `SystemTradingHarness` supporting configurable modes: `backtest`, `shadow`, `live`.
- [ ] Guarantees complete semantic parity across all modes for feature calculation, candidate ranking, LangChain decision logic, and Risk Engine constraints.
- [ ] Simulated exchange adapter accurately simulates order fills, order book depth consumption, slippage, and maker/taker fees in `shadow` mode without touching live trading endpoints.
- [ ] Backtest runner replays multi-timeframe historical data and produces reproducible equity curves and performance statistics.
- [ ] Implements automated end-of-session position liquidation that closes 100% of open coin positions into TMN before simulation/contest expiry.
- [ ] Tests verify end-to-end simulation runs, fill realism, and semantic consistency across modes.

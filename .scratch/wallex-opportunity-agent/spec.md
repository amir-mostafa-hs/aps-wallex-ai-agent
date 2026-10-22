# Spec: Wallex Opportunity Agent

Status: ready-for-agent

## Problem Statement

Participants in the StarCoach & Wallex AI Agent Hackathon need to deploy an autonomous trading agent that operates on a dedicated Wallex Credit Sub-Account (Package 183: 5,000,000 TMN credit, 0 collateral, 3-day duration, 0 daily fee). The agent must operate continuously on Spot markets without leverage, scan hundreds of trading pairs, independently identify viable trading opportunities across multiple time horizons, adaptively allocate capital, enforce strict multi-layer risk controls to prevent catastrophic liquidation (threshold: 900 TMN valuation), and generate auditable trade and loss analysis logs.

Previous trading bots or simplistic rule engines either flood single markets, rely on fragile hard-coded if/else rules, lack real AI decision-making, or give the LLM unrestricted and dangerous write-access to the exchange API, risking rapid capital depletion, API ban, or account liquidation. Furthermore, evaluation criteria heavily reward trading performance (P&L, max drawdown, uptime), technical quality (strategy logic, genuine AI usage, deterministic risk management), and reproducibility (reproducible backtests and shadow tests with matching execution semantics).

## Solution

Build the "Wallex Opportunity Agent" as a modular, single-process Python application that cleanly decouples market intelligence, AI decision orchestration, deterministic risk gating, and exchange order execution:

1. **Deterministic Market Scanning & Filtering**: Ingests official Wallex market metadata, merges the static local denylist (`docs/sources/inactive_markets.json`) with live package 183 unavailable markets to produce a clean 120-market Spot allowlist (Fail-Closed). Computes standardized multi-timeframe technical features (1m, 5m, 15m, 1h) and ranks candidates lightly on cached data every 15 seconds without polling the LLM per tick.
2. **LangChain Decision Agent (Structured Reasoning Only)**: An AI agent orchestrated via LangChain that evaluates only top candidates and open positions nearing review. It outputs a strictly typed `TradeIntent` using `TypedDict`/JSON Schema (no Pydantic models in domain code), choosing adaptively among whitelisted strategies (`momentum`, `trend_following`, `mean_reversion`) and horizon profiles (`FAST`, `INTRADAY_SHORT`, `INTRADAY`).
3. **Zero-Trust Independent Risk Engine**: Completely isolates the LLM from order execution. An independent, deterministic Risk Engine validates the semantic integrity of the `TradeIntent`, calculates position notional and stop distances based on portfolio equity, enforces exposure caps, cash reserve (minimum 50%), max drawdown, and rejects invalid, stale, or out-of-boundary intents.
4. **Idempotent Order Executor & Exchange Reconciler**: Submits client-tagged orders (`client_id`) to Wallex REST endpoints, guarantees reconciliation before retries, handles partial fills, strictly prevents self-trading, and maintains an internal position ledger.
5. **Continuous Telemetry & Loss Analysis**: Logs every candidate scan, AI rationale, risk rejection code, order execution fill, and fee. Deterministically computes Net Realized P&L (TMN) and Mark-to-Market Equity. Post-trade analysis categorizes losses into `confirmed`, `likely`, or `unknown` causes without hallucination.
6. **Unified Multi-Mode Execution**: Ensures 100% semantic parity across `backtest`, `shadow`, and `live` modes. Live trading is gated behind preflight health checks and explicit configuration.

---

## User Stories

### Market Universe & Allowlist
1. As a risk manager, I want the system to fetch active markets from Wallex Hector API and combine them with the local denylist and package 183 unavailable markets, so that no unauthorized or inactive symbol is ever analyzed or traded.
2. As a trader, I want the allowlist filter to operate fail-closed, so that if the denylist is missing or API responses are corrupted, live trading immediately shuts down.
3. As a developer, I want symbol formatting normalized (removing `/` and standardizing to uppercase), so that comparisons between local config and exchange symbols are exact.
4. As an operator, I want metadata like `amount_precision` and `price_precision` saved per symbol, so that subsequent orders are properly quantized to exchange step sizes.

### Data Ingestion & Feature Engineering
5. As an analyst, I want the system to warm up historical OHLCV candles from the official `/v1/udf/history` endpoint upon startup, so that multi-timeframe indicators have valid initial history.
6. As a system engineer, I want local resampling of 5m and 15m candles from 1m candles, so that API rate limits are conserved and indicators remain consistent.
7. As a quantitative developer, I want standardized feature generation (momentum, relative volume, ATR/volatility, spread in bps, and order book imbalance), so that candidates are ranked on objective criteria.
8. As a risk manager, I want stale data detection that flags quotes older than 5 seconds or snapshots older than 45 seconds, so that trading on outdated information is strictly blocked.
9. As a scanner, I want candidate ranking performed in a lightweight in-memory cache every 15 seconds, so that the LLM is not called for every symbol on every tick.

### AI Decision Making (LangChain)
10. As a judge, I want the Decision Agent to run via LangChain using a versioned prompt and structured output (`TypedDict` or JSON Schema), so that AI reasoning is structured, reproducible, and verifiable.
11. As a software architect, I want domain code to avoid direct Pydantic model definitions, so that dependency conflicts are minimized and semantic validation remains explicit.
12. As a portfolio manager, I want the agent to output a `TradeIntent` containing `action` (`NO_TRADE`, `BUY`, `HOLD`, `EXIT`), `strategy_id`, `horizon_profile`, `confidence`, `reason_code`, `decision_rationale`, `invalidation_condition`, and `evidence_ids`, so that every decision is backed by specific evidence.
13. As a safety engineer, I want the AI agent to have strictly zero write permissions or private exchange keys, so that it cannot bypass the Risk Engine or execute orders directly.
14. As an operator, I want the AI review cadence capped at a maximum of 3 calls per minute with at least 30 seconds between calls, so that LLM latency and budget are strictly controlled.
15. As a trader, I want the Decision Agent to evaluate open positions nearing invalidation or max holding time with higher priority than new entry candidates, so that existing positions are diligently managed.
16. As a system engineer, I want any LLM timeout, JSON syntax error, or unmapped action to default automatically to `NO_TRADE` or `HOLD`, so that execution failure never results in spurious orders.

### Risk Management & Portfolio Allocation
17. As a risk officer, I want the Risk Engine to independently calculate position sizing based on risk-to-stop, max position notional (15% equity), and max total exposure (40% equity), so that the account is never overleveraged.
18. As an auditor, I want a minimum cash reserve (default 50% equity) enforced before any new buy order is approved, so that liquidity is preserved.
19. As a risk officer, I want strict enforcement of maximum concurrent open positions (default 3), so that portfolio risk remains bounded.
20. As a trader, I want max holding time and hard stop-loss thresholds enforced deterministically by the system regardless of whether the LLM responds, so that capital is protected from market crashes.
21. As an operator, I want account liquidation protection that halts new entries if account equity falls near warning thresholds, so that the credit account is never liquidated by the exchange.
22. As a compliance officer, I want self-trading and wash-trading prevention that forbids opposite open orders or concurrent entries on the same symbol, so that fair competition rules are upheld.
23. As a developer, I want the Risk Engine to verify that estimated trading fees and slippage do not exceed the expected statistical edge, so that unprofitable trades are filtered out.

### Order Execution & Reconciliation
24. As an execution trader, I want every submitted order to carry a unique `client_id` persisted in the local database before dispatch, so that idempotency is guaranteed across restarts.
25. As a system engineer, I want any network timeout during order placement to trigger an order query by `client_id` rather than a blind retry, so that duplicate orders are strictly prevented.
26. As an accountant, I want partial fills to be tracked incrementally and reflected in the internal position ledger based on verified exchange fills, so that inventory is always accurate.
27. As a trader, I want `EXIT` orders to close 100% of the active position in the MVP, so that partial-exit state ambiguities are avoided.
28. As an operator, I want order sizes and limit prices checked against exchange `amount_precision` and `price_precision` before submission, so that the exchange never rejects orders for invalid formatting.
29. As a system engineer, I want pre-execution quote validation ensuring that quote data is fresher than 5 seconds, so that orders are not placed into stale books.

### Telemetry, Audit & Loss Analysis
30. As a data analyst, I want every scanner cycle, candidate score, AI prompt/response, risk approval/rejection, and order lifecycle event recorded in SQLite WAL, so that complete post-run forensics are possible.
31. As a contest judge, I want net realized P&L (in TMN) and mark-to-market equity tracked and reported separately, so that both scoring interpretations are transparently satisfied.
32. As a researcher, I want any losing trade to be audited and labeled with a post-mortem category (`confirmed`, `likely`, or `unknown`), so that strategy weaknesses can be studied without hallucinating external events.
33. As an operator, I want a status dashboard displaying account balance, equity, exposure, open positions, recent decisions, rejection rates, and system health, so that real-time oversight is effortless.

### Safety, Modes & Preflight
34. As a devops engineer, I want distinct `backtest`, `shadow`, and `live` modes sharing identical candidate, strategy, and risk semantics, so that simulation results match live behavior.
35. As a safety manager, I want `live` mode to be disabled by default and only activatable when `MODE=live`, `LIVE_TRADING_ENABLED=true`, `LIVE_PREFLIGHT_ACKNOWLEDGED=true`, and all automated preflight checks pass, so that accidents are prevented.
36. As a contest participant, I want an automated end-of-challenge liquidator that closes all open coin positions before the contest cutoff time, so that 100% of the final balance is realized in TMN.

---

## Implementation Decisions

### Module Boundaries & Responsibilities

1. **`MarketUniverse`**:
   - Ingests `GET /hector/web/v1/markets` and package 183 metadata.
   - Normalizes and unifies local denylist (`docs/sources/inactive_markets.json`) and live `unavailableMarkets`.
   - Filters out non-spot and inactive markets, producing an immutable `Allowlist` of tradeable symbols.
   - Provides symbol precision (`amount_precision`, `price_precision`) and tick/step size rules.

2. **`MarketDataStore` & `FeatureEngine`**:
   - Maintains rolling OHLCV candle buffers for 1m, 5m, 15m, and 1h intervals.
   - Fetches historical candles via `GET /v1/udf/history` during initialization.
   - Ingests real-time prices, order book depth (`GET /v1/depth`), and public trades.
   - Computes deterministic feature sets: price returns, ATR, relative volume, spread in bps, and orderbook imbalance.
   - Tracks data freshness; rejects snapshots older than 45 seconds and execution quotes older than 5 seconds.

3. **`CandidateScanner`**:
   - Runs every 15 seconds against the cached feature store.
   - Computes candidate ranking scores without invoking LLMs.
   - Selects the top 3 candidate symbols for AI review.
   - Maintains an AI Review Priority Queue where open positions nearing invalidation or holding limits take precedence over new entry candidates.

4. **`DecisionAgent` (LangChain Orchestrator)**:
   - Uses LangChain's modern agent runner (`create_agent`) with structured output.
   - Uses `TypedDict` and explicit JSON Schema for model output contract; does not declare domain Pydantic models.
   - Limits choices strictly to:
     - `action`: `NO_TRADE`, `BUY`, `HOLD`, `EXIT`
     - `strategy_id`: `momentum`, `trend_following`, `mean_reversion`, or `null`
     - `horizon_profile`: `FAST` (1–5 min), `INTRADAY_SHORT` (5–30 min), `INTRADAY` (30–120 min), or `null`
     - `reason_code`: `EDGE_INSUFFICIENT`, `SIGNAL_VALID`, `SIGNAL_INVALIDATED`, `RISK_CONTEXT`, `DATA_UNCERTAIN`, `OTHER`
   - Incorporates a pure Python semantic validator that checks value ranges, enum validity, evidence ID existence, and non-empty rationale.
   - Enforces fallback to `NO_TRADE` or `HOLD` upon timeout or validation failure.

5. **`PortfolioRiskEngine`**:
   - Acts as the authoritative gatekeeper between `TradeIntent` and `OrderExecutor`.
   - Evaluates portfolio equity, cash reserve, active exposure, and open positions.
   - Computes position sizing: `size = min(max_notional, risk_amount / stop_distance)`.
   - Validates that estimated execution cost (fees + spread + slippage) does not erode the expected edge.
   - Enforces hard stop loss, max drawdown pause, and portfolio kill switch.
   - Outputs a typed `RiskDecision` (Approved with calculated quantity, or Rejected with specific reason code).

6. **`OrderExecutor` & `Reconciler`**:
   - Only module authorized to communicate with Wallex private trading endpoints.
   - Generates and persists unique `client_id` before order submission.
   - Quantizes order quantity and limit price according to symbol precision rules.
   - Queries `GET /v1/account/orders/{client_id}` upon network timeout before attempting any retry.
   - Listens to order status updates, tracks partial fills, and updates the local position ledger only upon verified exchange fills.
   - Enforces cancel-and-confirm sequence before reversing positions to prevent self-trading.

7. **`PositionLedger` & `TradeAuditor`**:
   - Tracks open positions, average entry price, accumulated fills, and fees.
   - Calculates Net Realized P&L in TMN upon position exit, subtracting exact exchange fees.
   - Tracks Mark-to-Market Equity using live mid/bid quotes.
   - Generates post-trade loss analysis with evidence-backed cause classification (`confirmed`, `likely`, `unknown`).

8. **`Storage` & `Observability`**:
   - Uses SQLite with Write-Ahead Logging (WAL) for persistent audit trails.
   - FastAPI minimal service exposing health, status, portfolio metrics, and manual safety overrides (Pause, Resume, Emergency Flatten).

---

## Testing Decisions

### Seam Architecture

The system is designed with **one primary high-level seam** and two supporting sub-seams to maximize test depth while keeping implementation decoupled from tests:

```text
================================================================================
                    PRIMARY SEAM: System Trading Harness
================================================================================
 Input:  Simulated Market Feed / Recorded Cycles (ExchangeAdapter Mock/Replay)
 Action: Run Pipeline Cycle (Scan -> Agent -> Risk Engine -> Executor -> Ledger)
 Output: State Transitions in Event Store / Position Ledger / Order Records
================================================================================
```

1. **Primary High-Level Seam (`SystemTradingHarness`)**:
   - Injects a mock/recorded `ExchangeAdapter` providing market metadata, candles, depth, and order state transitions.
   - Drives the full synchronous or asynchronous cycle from candidate scanning to LangChain decision, risk validation, order placement, fill reconciliation, and P&L computation.
   - Verifies end-to-end external behavior:
     - Does an invalid market fail to produce orders?
     - Does an LLM hallucination fail to execute?
     - Does a network timeout trigger reconciliation rather than duplicate orders?
     - Does an account near liquidation cease all new entries?

2. **Sub-Seam 1 (`RiskEngineSeam`)**:
   - Pure function / deterministic object: `evaluate(intent, portfolio_state, quote) -> RiskDecision`.
   - Tests position sizing math, exposure caps, cash reserve checks, stop-loss triggers, and reject codes across boundary conditions.

3. **Sub-Seam 2 (`AgentContractValidatorSeam`)**:
   - Pure function: `validate_trade_intent(raw_model_dict, candidate_context) -> ValidatedIntent`.
   - Tests schema parsing, enum validation, out-of-bound numerical checks, evidence ID validation, and fallback to `NO_TRADE`.

### What Makes a Good Test
- **External Behavior Only**: Tests verify state transitions in the position ledger, database records, and dispatched order requests. No assertions on internal private helper variables.
- **Strict Reproducibility**: Market data feeds, timestamps, and LLM responses in tests are deterministic fixtures.
- **Fail-Closed Verification**: Every error path (stale quote, timeout, invalid symbol, corrupted JSON) must explicitly prove that no order was sent to the exchange.

---

## Out of Scope

- Multi-agent swarms, debates, or complex multi-agent graphs.
- Direct live order placement from LLM tools or write-capable prompt functions.
- Margin trading, leveraged positions, futures, or short selling.
- Real-time news scraping, Twitter/sentiment analysis, or macro fundamental data.
- Live automatic code rewriting or runtime prompt self-modification.
- Fancy multi-page frontend UI (only a lightweight, single-page FastAPI status dashboard).
- Multi-exchange routing or cross-exchange arbitrage.
- Partial position exits in MVP (MVP executes 100% position close on `EXIT`).

---

## Further Notes

### Open Questions & Technical Directives

1. **Stop Loss and Emergency Exit (محافظت از سرمایه و خروج اضطراری)**:
   - **Preflight Verification**: Verify whether Wallex Spot API reliably supports native server-side conditional orders (`STOP_LIMIT` / `STOP_MARKET`) via official documentation and, if feasible, non-trading validation.
   - **No Blind Reliance on Exchange STOP_LIMIT**: Do not assume exchange-side `STOP_LIMIT` is active or reliable until verified with live exchange proof.
   - **Local Watchdog Architecture**: Architect the system so that an independent **Local Watchdog** monitors tick/depth prices in real time and triggers deterministic emergency exits (market/limit sell orders) when stop conditions or invalidation thresholds are breached.
   - **Documented Risks of Local Watchdog**:
     - *Network Disconnection*: Loss of internet/socket connection between the agent and Wallex servers prevents timely stop execution.
     - *Process Crash/Halt*: Unexpected process kill, OOM, or server reboot temporarily disables watchdog monitoring.
     - *Price Staleness / Ingestion Lag*: Delayed WebSocket or REST polling may cause stops to trigger late, leading to higher slippage.
     - *Order Dispatch / Rejection Failure*: Emergency sell orders could be rejected due to exchange rate limits or sudden market halts.
   - **Strict LLM Decoupling**: Risk controls, hard stop-losses, and emergency exit triggers must **never** depend on an LLM re-evaluation or wait for a prompt response.
   - **Pre-Live Verification**: The emergency exit mechanism must be fully simulated and verified before `live` mode can be unlocked.

2. **Minimum Order Value (حداقل ارزش سفارش - Min Notional)**:
   - **Initial Suggested Defaults Only**: The values `100,000 TMN` for TMN pairs and `10 USDT` for USDT pairs are strictly initial suggested configurable defaults (`DEFAULT_MIN_NOTIONAL_TMN`, `DEFAULT_MIN_NOTIONAL_USDT`); they must **never** be asserted as official Wallex minimums.
   - **Market-Specific Verification**: The actual minimum order notional, step size, and precision constraints for each traded market must be verified from official Wallex documentation or real API response metadata.
   - **Fail-Closed on Unverified Markets**: If the true minimum order notional cannot be verified for a specific symbol, real order placement for that market is strictly prohibited. Unverified numbers must never be guessed.
   - **Explicit Currency Units**: Maintain strict, explicit separation between currencies (`TMN` / Toman, `IRR` / Rials, and `USDT` / Tether). All internal conversions must be explicit to prevent scale mismatch.

3. **Credit Account Expiration (زمان انقضای اعتبار حساب هکاتون)**:
   - **Preflight Verification of `expireAt`**: Query `GET /v1/prop/user/packages/active` or check official sub-account endpoints during preflight to determine the authoritative end-of-credit timestamp (`expireAt`) and exact timezone (e.g., UTC / `Asia/Tehran`).
   - **No Rigid 72-Hour Assumption**: Do not treat the general 72-hour assumption as an unverified absolute fact.
   - **Continuous Remaining-Time Monitoring**: The system must continuously track remaining credit duration and halt all new trade entries before expiration.
   - **Pre-Expiry Liquidation Policy**: Closing all coin positions at least **2 hours before expiration** is currently a proposed, configurable policy (`PRE_EXPIRY_EXIT_HOURS=2.0`), not a confirmed contest mandate. It is adopted as a conservative default, pending user confirmation.
   - **Block Live if Expiry Unverified**: If the exact account expiration time cannot be definitively verified, `live` mode enablement remains blocked.

---

### Preflight Checklist (Gatekeepers for Live Mode)

Before `MODE=live` and `LIVE_TRADING_ENABLED=true` can be activated, every check below must pass:

- [ ] **API Key & Credit Sub-Account Verified**: API key proven to have `TRADE` permissions under the dedicated credit sub-account with `sub-account-client-id` header validated.
- [ ] **Market Allowlist Computed**: Local denylist (`docs/sources/inactive_markets.json`) merged with package 183 `unavailableMarkets`; only active Spot markets passing the filter are allowed.
- [ ] **Min Notional & Precision Validated**: Step sizes, price ticks, and minimum order values verified from API for all target symbols; unverified symbols excluded.
- [ ] **Emergency Exit & Watchdog Validated**: Local Watchdog simulated and verified; emergency market/limit sell tested without LLM dependency; watchdog failure risks documented.
- [ ] **Account Expiry Monitored**: Exact `expireAt` timestamp and timezone recorded; automatic entry cutoff and pre-expiry position flattening policy configured and confirmed.
- [ ] **Reconciliation & Idempotency Verified**: Restart test confirms open orders, position ledger, and cash balances reconcile with exchange without creating duplicate orders.
- [ ] **Kill Switch & Safety Gates Active**: Account equity liquidation floor (900 TMN) and max drawdown hard stops confirmed operational.


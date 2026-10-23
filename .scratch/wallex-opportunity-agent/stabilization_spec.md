# Specification: Wallex Opportunity Agent — Data, Backtest, Integration & UI Stabilization

## Problem Statement

The Wallex Opportunity Agent currently suffers from stability and consistency problems across several key areas:
1. **Market Data & Pricing Inconsistencies:** The Shadow runner and other components still rely on hardcoded default prices (`base_market_defaults` in `cli.py` with BTC at 4.5B TMN and USDT at 70,000 TMN with synthetic modulo drift), while the live Wallex market price for USDT/TMN is ~272,800 TMN.
2. **Broken Equity Curve Visualization:** The dashboard SVG equity chart renders `NaN` coordinates because of a property name mismatch between the backend (`equity_tmn`) and the frontend renderer (`p.total_equity`), combined with inadequate handling of single-point or flat equity lines.
3. **Run Mode Boundaries:** Shadow mode should consume live market data without order dispatch capability, whereas Backtest mode must operate strictly on historical OHLCV data without current live ticker contamination or synthetic price generation in production paths.
4. **Duplicated Configuration & Defaults:** Stop-loss, take-profit, holding periods, and initial equity defaults are duplicated across the frontend HTML, backend endpoints, harness, and strategy classes.
5. **Dashboard Typography & Presentation:** The Persian RTL dashboard relies on system fonts or generic fallbacks rather than a reliable, locally bundled Vazirmatn font.

## Solution

1. **Authoritative Market Data Adapter:** Build a consolidated `WallexMarketDataAdapter` that queries official Wallex endpoints (`GET /v1/markets` and `GET /hector/web/v1/markets`), extracting executable bid/ask spreads, live last trade prices, quote assets, and precision rules, completely replacing hardcoded fallback defaults in live and shadow operations.
2. **Canonical Financial Contract & Currency Conversion:** Maintain exact quote asset identification. When reporting in TMN, use live or timestamp-matched `USDTTMN` exchange rates to convert USDT-quoted markets into TMN with high-precision `Decimal` math.
3. **Rigid Mode Segregation:** Backtest runs strictly on verified historical candles with zero lookahead; Shadow mode consumes live market data with zero order submission capability.
4. **Consolidated BacktestRunResult Schema:** Unify the schema returned by `/api/backtest/run` and consumed by UI cards, trade tables, and the equity chart.
5. **Fixed SVG Equity Chart:** Reconcile property names (`equity_tmn` / `total_equity`), validate finite numeric values, and provide honest zero/flat-state rendering without `NaN`.
6. **Single Source of Truth for Settings:** Define a single parameter validation schema for strategies and risk bounds shared by frontend and backend.
7. **Polished Persian RTL Interface with Local Vazirmatn:** Package the official Vazirmatn font locally within the static asset pipeline and optimize the dashboard for Iranian financial traders.

## User Stories

1. As a trader running the agent in Shadow mode, I want the system to fetch live spot market prices and top-of-book bid/ask from the official Wallex API, so that trading opportunities reflect actual market conditions.
2. As a trader, I want the USDT/TMN market price to reflect the actual exchange rate (~272,800 TMN) rather than a stale 70,000 TMN default, so that portfolio valuation and USDT conversions are accurate.
3. As an analyst evaluating backtest results, I want the equity curve chart to render a clean SVG line without `NaN` errors or broken coordinates, so that I can see performance over time.
4. As an analyst running a backtest, I want my selected strategy in the dropdown to execute its actual algorithmic logic rather than simply relabeling trades, so that comparative backtests are meaningful.
5. As an analyst, I want the stop-loss, take-profit, holding time, and simulation length selected in the UI to be respected by the backtest engine and recorded in the result metadata, so that I can test different risk parameters.
6. As a compliance auditor, I want a guarantee that running in Shadow mode cannot submit live orders to the exchange, so that capital is never put at risk during simulation.
7. As a trader reviewing trade logs, I want gross P&L, fees, and net P&L to reconcile exactly according to standard accounting rules in Toman, so that there is zero mathematical ambiguity.
8. As a user viewing the web dashboard, I want the Persian RTL interface to be rendered with the crisp Vazirmatn font without requiring external CDN downloads, so that the dashboard loads reliably in all network environments.
9. As an analyst, I want each backtest run to produce a unique `run_id` with an isolated state, so that results from previous runs never leak into new runs.
10. As a trader, I want markets quoted in USDT (e.g. BTCUSDT) to have their notionals and P&L converted to TMN using the real USDTTMN price, so that currency units are never mixed.
11. As a system operator, I want server-side validation to reject invalid or negative backtest parameters with clear error messages, so that bad inputs cannot cause crashes.
12. As an operator running with an unconfigured or disconnected API, I want the system to fail closed and mark prices as stale rather than silently injecting synthetic price oscillations, so that fake data is never mistaken for reality.

## Implementation Decisions

- **Authoritative Market Data Adapter:**
  - Create `WallexMarketDataAdapter` in `src/wallex_agent/market_data_adapter.py`.
  - Polling strategy: Primary polling using `GET /v1/markets` which provides full symbol dictionaries with `stats.bidPrice`, `stats.askPrice`, `stats.lastPrice`, `stats.24h_volume`, `minNotional`, and precisions.
  - Secondary metadata enrichment via `GET /hector/web/v1/markets` for spot active status and categories.
  - Fail-closed behavior: When the live API fails or network drops, mark data as stale (`is_stale = True`) and prevent new entries. Never inject hardcoded 70,000 TMN or synthetic modulo drifts into production paths.

- **Mode Segregation:**
  - `ShadowOrderExecutor` strictly rejects/logs simulated orders without referencing or holding network execution credentials.
  - Synthetic price generators are quarantined to `tests/` fixtures and flagged as simulated.

- **Financial Service & Schema Reconciliation:**
  - Canonical `BacktestRunResult` TypedDict containing `run_id`, `strategy_id`, `parameters`, `initial_capital_tmn`, `final_equity_tmn`, `gross_pnl_tmn`, `total_fees_tmn`, `net_pnl_tmn`, `roi_pct`, `win_rate_pct`, `trades`, and `equity_curve`.
  - Equity curve points standardized as: `{"timestamp": float, "total_equity": float, "equity_tmn": float}` ensuring backward and forward compatibility with both `p.total_equity` and `p.equity_tmn`.

- **SVG Chart Renderer Fix:**
  - Robust parser extracting `p.total_equity ?? p.equity_tmn ?? initialCapital`.
  - Guard against `NaN`, infinite, or missing values.
  - Graceful handling of single-point runs or flat equity lines (`maxEq === minEq`) by enforcing a minimum visual range buffer.

- **Font & RTL Localization:**
  - Bundle `vazirmatn.woff2` locally in `src/wallex_agent/static/fonts/` (or embedded base64 CSS font-face) and serve directly from FastAPI.
  - Apply clean Persian number formatting (`Intl.NumberFormat('fa-IR')` or localized `toLocaleString`) in UI cards.

## Testing Decisions

- Test only external behavior and contracts, avoiding testing internal implementation details.
- Unit tests for the new `WallexMarketDataAdapter` with recorded live responses from Wallex `/v1/markets` and `/hector/web/v1/markets`.
- Unit tests for currency conversions (USDT to TMN using live/historical USDTTMN rate).
- Integration test proving `ShadowOrderExecutor` produces zero exchange network calls.
- Backtest parameter flow tests verifying that changing UI parameters changes the simulation execution and result metadata.
- SVG chart renderer tests ensuring no `NaN` in SVG output across empty, single-point, flat, and multi-point curves.

## Out of Scope

- Futures, margin trading, and short selling (competition rules restrict trading strictly to Spot long-only).
- Modifying Wallex official credit package rules.
- Third-party external font CDN hosting.

## Further Notes

All changes must maintain backward compatibility with existing tests and preserve all 95 currently passing tests.

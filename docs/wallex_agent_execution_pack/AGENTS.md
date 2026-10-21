# Agent Operating Rules

Read `README_FA.md`, `docs/DECISION_REGISTER_FA.md`, `docs/SOURCE_MATERIALS_AND_GAPS_FA.md`, `docs/AGENT_CONTRACT_FA.md`, `docs/SPEC_FA.md`, `docs/ARCHITECTURE_FA.md`, `docs/MARKET_SCANNING_DECISION_LOGIC_FA.md`, `docs/TODO_48H_FA.md` before changing code.

- Do not guess Wallex endpoints or response fields; verify against official docs and `docs/WALLEX_API_NOTES.md`.
- Keep all trading API secrets in environment variables, never logs or Git.
- Default to shadow mode. Live mode requires `MODE=live`, `LIVE_TRADING_ENABLED=true`, `LIVE_PREFLIGHT_ACKNOWLEDGED=true`, and completed preflight. This is a one-time startup gate, not manual confirmation per order.
- Strategy/AI produces a typed TradeIntent only. Risk Engine must approve before Order Executor can submit.
- Never retry an ambiguous order submission before reconciling exchange state.
- No order without market allowlist, balance, quantity/price precision, min notional, exposure and self-trade checks.
- Use TDD for risk sizing, order state transitions, duplicate prevention, fill reconciliation and P&L.
- Report only tests that actually ran. Don't assert profitability without measured results.
- Each change should be a small, demonstrable vertical slice; keep dependencies lean.

- Keep `docs/AGENT_CONTRACT_FA.md` as the single source of truth for Agent `action` and `horizon_profile` values.
- Do not define/import domain Pydantic models; use LangChain structured output with TypedDict/JSON Schema plus explicit semantic validation. Transitive dependencies must not be force-uninstalled.
- If original `assets.md` denylist is absent or not reviewed, fail closed and keep live trading disabled.
- Treat market-summary ranking data and pre-submit execution quote as having different freshness limits. Re-fetch/validate fresh execution data before submitting an order.
- There is no trade-by-trade human approval in live operation; one-time human preflight/config enablement is still required. Once live is enabled, automated orders must always pass the deterministic Risk Engine.


## Source of truth and credit-account safety

- Original challenge sources are in `source_materials/originals/`; read all four before changing strategy, symbols, scoring, or end-of-contest behavior.
- `source_materials/derived/inactive_markets.json` is a derived denylist from the 345 market pairs in `assets.md`, not an allowlist. Cross-check with live API active Spot markets and account capabilities.
- The PDF describes 0 input assets + 5,000,000 Toman credit for 3 days, API management as available in credit, trading-bot/futures capability as unavailable, and a severe liquidation condition. Confirm actual fee, liquidation threshold, permissions, and expiry time before Live.
- Where source text conflicts (realized Toman/no coin at end versus account valuation/unrealized P&L), log both metrics and get organizer confirmation; do not silently resolve the conflict.

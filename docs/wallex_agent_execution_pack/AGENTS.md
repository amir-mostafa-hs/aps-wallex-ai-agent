# Agent Operating Rules

Read `README_FA.md` and `docs/SPEC_FA.md`, `docs/ARCHITECTURE_FA.md`, `docs/TODO_48H_FA.md` before changing code.

- Do not guess Wallex endpoints or response fields; verify against official docs and `docs/WALLEX_API_NOTES.md`.
- Keep all trading API secrets in environment variables, never logs or Git.
- Default to shadow mode. Live mode requires explicit configuration and completed preflight.
- Strategy/AI produces a typed TradeIntent only. Risk Engine must approve before Order Executor can submit.
- Never retry an ambiguous order submission before reconciling exchange state.
- No order without market allowlist, balance, quantity/price precision, min notional, exposure and self-trade checks.
- Use TDD for risk sizing, order state transitions, duplicate prevention, fill reconciliation and P&L.
- Report only tests that actually ran. Don't assert profitability without measured results.
- Each change should be a small, demonstrable vertical slice; keep dependencies lean.

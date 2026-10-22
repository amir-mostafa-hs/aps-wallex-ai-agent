# 09: SQLite WAL Telemetry, Dual P&L & Trade Auditor

**What to build:**
A persistent event-logging and post-trade auditing subsystem powered by SQLite in WAL mode. It records every scanner cycle, candidate score, AI decision prompt/response, risk approval/rejection, and order lifecycle event. It deterministically computes both Net Realized P&L (in TMN with exact exchange fee deduction) and Mark-to-Market Equity, and conducts post-trade loss analysis with evidence-backed cause classification (`confirmed`, `likely`, `unknown`).

**Blocked by:**
08: Order Executor, Client ID Tracking & Reconciliation

**Status:**
resolved

## Acceptance Criteria

- [x] SQLite database configured with Write-Ahead Logging (WAL) and synchronous normal mode for concurrent read/write performance.
- [x] Schema stores immutable audit logs for scanner cycles, AI reasoning payloads, risk evaluation records, order events, and position transitions.
- [x] Deterministically calculates Net Realized P&L in TMN upon position exit, subtracting maker/taker exchange fees.
- [x] Continuously tracks and logs Mark-to-Market Equity using real-time bid/ask valuation for open positions.
- [x] Audits losing trades and generates post-trade analysis categorizing causes into `confirmed`, `likely`, or `unknown` based on recorded market data without LLM hallucination.
- [x] Never logs secrets, private API keys, or raw authentication tokens.
- [x] Unit tests verify event insertion, P&L accounting math against test fills, and loss categorization logic.

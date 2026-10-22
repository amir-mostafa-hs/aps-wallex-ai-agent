# 12: Status Dashboard & Safety Control Interface

**What to build:**
A lightweight, authenticated FastAPI web service providing real-time visibility and human supervisory control over the running agent. It visualizes account balance, equity, cash reserve, active exposure, open positions, recent candidate rankings, AI reasoning excerpts, and risk rejection rates, while providing secure operator controls for Pause New Entries, Resume, and Emergency Flatten.

**Blocked by:**
09: SQLite WAL Telemetry, Dual P&L & Trade Auditor, 10: Multi-Mode Engine (Backtest, Shadow & Simulated Replay)

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] FastAPI service exposes authenticated read-only endpoints and a minimal single-page HTML status dashboard.
- [ ] Displays execution mode (`backtest`, `shadow`, `live`), system state (`RUNNING`, `PAUSED`, `SAFE-STOP`), and uptime.
- [ ] Displays financial metrics: starting balance, available cash, equity, realized net P&L, fees, and max drawdown.
- [ ] Displays active portfolio state: open positions, average entry prices, current P&L, and open orders.
- [ ] Displays telemetry logs: recent candidate scores, AI decisions with confidence/rationale, and Risk Engine reject codes.
- [ ] Provides authenticated safety action endpoints:
  - `POST /api/control/pause`: pauses new trade entries while maintaining position management.
  - `POST /api/control/resume`: resumes entries after operator review.
  - `POST /api/control/flatten`: triggers immediate orderly closing of all open positions.
- [ ] Endpoints require API token or basic auth; endpoints cannot be accessed unauthenticated.
- [ ] Tests verify status endpoint serialization, auth enforcement, and control endpoint state transitions.

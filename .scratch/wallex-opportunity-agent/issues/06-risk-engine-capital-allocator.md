# 06: Deterministic Portfolio Risk Engine & Sizing

**What to build:**
A deterministic, pure-Python Portfolio Risk Engine that serves as the unbypassable gatekeeper between `TradeIntent` suggestions and order execution. It validates portfolio state against account equity (5M TMN credit baseline), sizes positions based on risk-to-stop and max position notional (15%), checks min cash reserve (50%), max total exposure (40%), max concurrent positions (3), min notional thresholds, and liquidation safety floors (warning at 1,000 TMN, liquidation at 900 TMN), emitting a typed `RiskDecision`.

**Blocked by:**
01: Project Foundation, Core Types & Config

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Calculates order quantity using risk-to-stop formula bounded by max position notional limit (`min(max_notional, risk_amount / stop_distance)`).
- [ ] Enforces maximum position notional cap (default 15% equity) and maximum total exposure cap (default 40% equity).
- [ ] Guarantees minimum cash reserve (default 50% equity) remains unallocated.
- [ ] Enforces maximum open concurrent positions (default 3 positions).
- [ ] Validates that expected statistical edge exceeds estimated execution friction (fee + spread + slippage).
- [ ] Enforces account liquidation safety floor: halts all new entries if equity approaches warning threshold (1,000 TMN) or liquidation floor (900 TMN).
- [ ] Rejects intents on symbols with unverified minimum notional values or unresolved open orders.
- [ ] Emits a typed `RiskDecision` (Approved with calculated quantity, or Rejected with specific machine-readable reject code).
- [ ] Comprehensive unit tests cover sizing math, boundary limits, cash reserves, and rejection cases across diverse equity levels.

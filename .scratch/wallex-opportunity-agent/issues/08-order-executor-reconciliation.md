# 08: Order Executor, Client ID Tracking & Reconciliation

**What to build:**
The single authoritative order execution module that communicates with Wallex private trading endpoints. It generates unique, persistent client order IDs (`client_id`), quantizes price and quantity against exchange precision rules, queries order state upon network timeouts rather than issuing blind retries, manages partial fills, and updates the local position ledger only on verified exchange fills. It also enforces cancel-and-confirm execution to prevent self-trading during position reversals.

**Blocked by:**
01: Project Foundation, Core Types & Config, 06: Deterministic Portfolio Risk Engine & Sizing

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Generates unique, cryptographically random `client_id` for every order and records it locally prior to network transmission.
- [ ] Quantizes price and quantity according to target market `price_precision` and `amount_precision`.
- [ ] Submits orders to Wallex `POST /v1/account/orders` with required `sub-account-client-id` and `X-API-Key` headers.
- [ ] On network timeout or connection reset, executes reconciliation via `GET /v1/account/orders/{client_id}` before taking any retry action; blind duplicate order submission is impossible.
- [ ] Supports partial fills (`PARTIALLY_FILLED`), tracking cumulative executed quantity, executed sum, and fee deductions.
- [ ] Updates internal position ledger and cash balance only upon receipt of verified exchange fill events.
- [ ] Enforces self-trade prevention: cancels and confirms cancellation of any opposing open order before dispatching a reverse trade.
- [ ] Unit and mock integration tests cover timeout reconciliation, partial fill accumulation, precision formatting, and self-trade prevention.

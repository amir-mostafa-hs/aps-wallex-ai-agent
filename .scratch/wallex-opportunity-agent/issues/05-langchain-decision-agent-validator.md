# 05: LangChain Decision Agent & Semantic Validator

**What to build:**
A dedicated AI Decision Agent orchestrated via LangChain's modern `create_agent` pattern using structured output (`TypedDict` or JSON Schema) to evaluate candidate snapshots or open positions. The agent outputs a structured `TradeIntent` containing action, strategy ID, horizon profile, confidence, evidence IDs, and textual rationale. A pure Python semantic validator rigorously checks the returned structure and safely converts timeouts or validation failures into `NO_TRADE` or `HOLD`.

**Blocked by:**
01: Project Foundation, Core Types & Config

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Decision Agent is orchestrated with LangChain using a versioned system prompt and structured output schema.
- [ ] Contract limits outputs strictly to approved enums:
  - `action`: `NO_TRADE`, `BUY`, `HOLD`, `EXIT`
  - `strategy_id`: `momentum`, `trend_following`, `mean_reversion`, or `null`
  - `horizon_profile`: `FAST`, `INTRADAY_SHORT`, `INTRADAY`, or `null`
  - `reason_code`: `EDGE_INSUFFICIENT`, `SIGNAL_VALID`, `SIGNAL_INVALIDATED`, `RISK_CONTEXT`, `DATA_UNCERTAIN`, `OTHER`
- [ ] Pure Python validator verifies schema conformity, numerical bounds (confidence 0..1, positive stop distances), evidence ID existence, and non-empty rationale.
- [ ] Agent has strictly zero private exchange API keys or order dispatch tools.
- [ ] Any LLM timeout, malformed JSON, or out-of-range value cleanly falls back to `NO_TRADE` (for candidates) or `HOLD` (for existing positions).
- [ ] Tests verify structured output parsing, validator rules, and fallback safety behavior with mocked LLM responses.

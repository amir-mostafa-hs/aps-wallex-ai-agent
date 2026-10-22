# 01: Project Foundation, Core Types & Config

**What to build:**
Set up the fundamental Python package skeleton, automated test environment (`pytest`), structured configuration loader from environment variables (`.env`), and pure Python typed contracts (`TypedDict`) for all domain entities (`MarketInfo`, `MarketSnapshot`, `Candidate`, `TradeIntent`, `RiskDecision`, `OrderRecord`, `PositionRecord`, `TradeRecord`). The system must enforce business logic constraints and schema shapes using explicit pure-Python semantic validators without defining or depending on domain Pydantic models.

**Blocked by:**
None (can start immediately)

**Status:**
ready-for-agent

## Acceptance Criteria

- [ ] Python project structure is established with a clean src layout, test suite configuration, and linting rules.
- [ ] Environment configuration loader safely parses trading variables, API credentials, risk limits, and execution modes with fail-closed defaults.
- [ ] Domain models are defined using `typing.TypedDict` and JSON Schema definitions covering all lifecycle entities.
- [ ] Explicit semantic validator functions validate field types, enum values, value ranges, and required relationships in pure Python.
- [ ] Zero domain Pydantic models are imported or declared in domain code.
- [ ] Unit tests verify configuration loading, default fallbacks, and schema validation across valid and invalid inputs.

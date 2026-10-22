"""LangChain Decision Agent and structured TradeIntent generation."""
from __future__ import annotations
import uuid
from typing import Any, Mapping
from wallex_agent.domain.types import TradeIntent
from wallex_agent.domain.validation import validate_trade_intent, ValidationError

SYSTEM_PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = """You are the Wallex Opportunity Decision Agent.
Your responsibility is to analyze structured quantitative market evidence for Spot trading opportunities and decide whether to BUY, HOLD, EXIT, or take NO_TRADE.
Rules:
1. Spot trading only without leverage. No short selling.
2. Actions:
   - NO_TRADE: Do not enter a new trade in this cycle.
   - BUY: Enter a new Spot buy position on an approved candidate.
   - HOLD: Maintain an existing position without modifying orders.
   - EXIT: Propose orderly closing of the full existing position.
3. Allowed strategies: momentum, trend_following, mean_reversion.
4. Allowed horizon profiles: FAST (1-5m), INTRADAY_SHORT (5-30m), INTRADAY (30-120m).
5. For BUY, you must provide positive stop_distance_pct, invalidation_condition, and evidence_ids from the given context.
6. Never invent or hallucinate evidence_ids that were not provided in the input context.
7. Return strictly valid structured data matching the TradeIntent schema.
"""

TRADE_INTENT_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "contract_version": {"type": "string"},
        "decision_id": {"type": "string"},
        "cycle_id": {"type": "string"},
        "symbol": {"type": "string"},
        "action": {"type": "string", "enum": ["NO_TRADE", "BUY", "HOLD", "EXIT"]},
        "strategy_id": {"type": ["string", "null"], "enum": ["momentum", "trend_following", "mean_reversion", None]},
        "horizon_profile": {"type": ["string", "null"], "enum": ["FAST", "INTRADAY_SHORT", "INTRADAY", None]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason_code": {
            "type": "string",
            "enum": ["EDGE_INSUFFICIENT", "SIGNAL_VALID", "SIGNAL_INVALIDATED", "RISK_CONTEXT", "DATA_UNCERTAIN", "OTHER"],
        },
        "decision_rationale": {"type": "string"},
        "invalidation_condition": {"type": ["string", "null"]},
        "stop_distance_pct": {"type": ["number", "null"], "minimum": 0.0},
        "take_profit_distance_pct": {"type": ["number", "null"], "minimum": 0.0},
        "max_holding_minutes": {"type": ["integer", "null"], "minimum": 1},
        "parameter_overrides": {"type": "object"},
        "evidence_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "contract_version",
        "decision_id",
        "cycle_id",
        "symbol",
        "action",
        "confidence",
        "reason_code",
        "decision_rationale",
        "evidence_ids",
    ],
    "additionalProperties": False,
}


class DecisionAgent:
    """Orchestrates structured AI trading decisions with zero private execution access."""

    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client

    def decide(self, context: Mapping[str, Any]) -> TradeIntent:
        """Invokes the decision model or returns a safe deterministic fallback intent."""
        symbol = str(context.get("symbol", "")).strip().upper()
        cycle_id = str(context.get("cycle_id", ""))
        has_open_position = bool(context.get("has_open_position", False))
        evidence_ids = list(context.get("evidence_ids", []))
        decision_id = f"dec-{uuid.uuid4().hex[:8]}"

        default_fallback_action = "HOLD" if has_open_position else "NO_TRADE"

        if self.llm_client is None:
            return self._build_fallback(
                symbol=symbol,
                cycle_id=cycle_id,
                decision_id=decision_id,
                action=default_fallback_action,
                reason="No LLM client configured; deterministic fallback",
                evidence_ids=evidence_ids,
            )

        try:
            prompt_input = {
                "system": SYSTEM_PROMPT,
                "context": context,
            }
            raw_response = self.llm_client.invoke(prompt_input)
            if not isinstance(raw_response, Mapping):
                raise ValidationError(f"LLM returned unexpected response type: {type(raw_response).__name__}")

            # Validate semantics in pure Python
            validated = validate_trade_intent(
                raw=raw_response,
                allowed_evidence_ids=evidence_ids,
            )
            return validated

        except Exception as exc:
            # Safe fail-closed fallback
            return self._build_fallback(
                symbol=symbol,
                cycle_id=cycle_id,
                decision_id=decision_id,
                action=default_fallback_action,
                reason=f"AI invocation fallback: {str(exc)}",
                evidence_ids=evidence_ids,
            )

    def _build_fallback(
        self,
        symbol: str,
        cycle_id: str,
        decision_id: str,
        action: str,
        reason: str,
        evidence_ids: list[str],
    ) -> TradeIntent:
        """Constructs a deterministic safe fallback TradeIntent."""
        return {
            "contract_version": "1.0",
            "decision_id": decision_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": action,  # type: ignore
            "strategy_id": None,
            "horizon_profile": None,
            "confidence": 0.0,
            "reason_code": "DATA_UNCERTAIN",
            "decision_rationale": reason,
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": list(evidence_ids),
        }

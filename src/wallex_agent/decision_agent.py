"""LangChain Decision Agent and structured TradeIntent generation."""
from __future__ import annotations
import os
import json
import uuid
import httpx
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


class HTTPOpenAIClient:
    """Zero-dependency HTTP client for OpenAI-compatible LLM endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://ai.boxapi.ir/ai/v1",
        model: str = "gpt-6-luna",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def invoke(self, prompt_input: Mapping[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        system_content = prompt_input.get("system", SYSTEM_PROMPT)
        context_data = prompt_input.get("context", {})

        user_content = (
            f"Evaluate trading opportunity for context:\n{json.dumps(context_data, ensure_ascii=False)}\n"
            "Return JSON matching TradeIntent with keys: contract_version, decision_id, cycle_id, symbol, action, "
            "strategy_id, horizon_profile, confidence, reason_code, decision_rationale, invalidation_condition, "
            "stop_distance_pct, take_profit_distance_pct, max_holding_minutes, parameter_overrides, evidence_ids."
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }

        resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API status {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        raw_dict = json.loads(content)

        # Normalize reason_code if model returned free text
        valid_reasons = {"EDGE_INSUFFICIENT", "SIGNAL_VALID", "SIGNAL_INVALIDATED", "RISK_CONTEXT", "DATA_UNCERTAIN", "OTHER"}
        if raw_dict.get("reason_code") not in valid_reasons:
            raw_dict["reason_code"] = "OTHER"

        # Sanitize parameter_overrides
        if isinstance(raw_dict.get("parameter_overrides"), dict):
            allowed_keys = {"stop_distance_pct", "take_profit_distance_pct", "max_holding_minutes"}
            raw_dict["parameter_overrides"] = {
                k: v for k, v in raw_dict["parameter_overrides"].items()
                if k in allowed_keys and isinstance(v, (int, float)) and v > 0
            }
        else:
            raw_dict["parameter_overrides"] = {}

        return raw_dict


class DecisionAgent:
    """Orchestrates structured AI trading decisions with zero private execution access."""

    def __init__(self, llm_client: Any = None, heuristic_mode: bool = False) -> None:
        if llm_client is None and not heuristic_mode:
            llm_key = os.getenv("LLM_API_KEY", "").strip()
            if llm_key:
                base_url = os.getenv("LLM_BASE_URL", "https://ai.boxapi.ir/ai/v1")
                model = os.getenv("LLM_MODEL", "gpt-6-luna")
                self.llm_client = HTTPOpenAIClient(api_key=llm_key, base_url=base_url, model=model)
            else:
                self.llm_client = None
        else:
            self.llm_client = llm_client
        self.heuristic_mode = heuristic_mode

    def decide(self, context: Mapping[str, Any]) -> TradeIntent:
        """Invokes the decision model or returns a safe deterministic fallback intent."""
        symbol = str(context.get("symbol", "")).strip().upper()
        cycle_id = str(context.get("cycle_id", ""))
        has_open_position = bool(context.get("has_open_position", False))
        evidence_ids = list(context.get("evidence_ids", []))
        decision_id = f"dec-{uuid.uuid4().hex[:8]}"

        default_fallback_action = "HOLD" if has_open_position else "NO_TRADE"

        if self.llm_client is None:
            if self.heuristic_mode:
                features = context.get("features", {})
                ret = float(features.get("return_pct", 0.0))
                rvol = float(features.get("relative_volume", 0.0))
                if ret > 0.0 and rvol >= 1.0 and not has_open_position:
                    return {
                        "contract_version": "1.0",
                        "decision_id": decision_id,
                        "cycle_id": cycle_id,
                        "symbol": symbol,
                        "action": "BUY",
                        "strategy_id": "momentum",
                        "horizon_profile": "FAST",
                        "confidence": 0.85,
                        "reason_code": "SIGNAL_VALID",
                        "decision_rationale": f"Quantitative momentum trigger (ret={ret:.2f}%, rvol={rvol:.2f})",
                        "invalidation_condition": "Loss of short-term volume momentum",
                        "stop_distance_pct": 1.0,
                        "take_profit_distance_pct": 2.0,
                        "max_holding_minutes": 5,
                        "parameter_overrides": {},
                        "evidence_ids": list(evidence_ids),
                    }
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

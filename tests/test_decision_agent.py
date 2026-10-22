import pytest
from unittest.mock import MagicMock
from wallex_agent.domain.types import TradeIntent
from wallex_agent.decision_agent import DecisionAgent, SYSTEM_PROMPT_VERSION


def test_decision_agent_successful_buy_decision():
    # Mock LLM provider that returns valid structured output
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "contract_version": "1.0",
        "decision_id": "dec-100",
        "cycle_id": "cyc-50",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.88,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Strong 5m momentum breakout with 3x volume expansion",
        "invalidation_condition": "Close below 5m swing low",
        "stop_distance_pct": 0.9,
        "take_profit_distance_pct": 1.8,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["snap-btc-1", "feat-btc-1"],
    }

    agent = DecisionAgent(llm_client=mock_llm)
    candidate_context = {
        "symbol": "BTCTMN",
        "cycle_id": "cyc-50",
        "features": {"return_pct": 2.1, "relative_volume": 3.2, "volatility": 1.1},
        "spread_bps": 22.0,
        "evidence_ids": ["snap-btc-1", "feat-btc-1"],
        "has_open_position": False,
    }

    intent = agent.decide(candidate_context)
    assert intent["action"] == "BUY"
    assert intent["strategy_id"] == "momentum"
    assert intent["horizon_profile"] == "FAST"
    assert intent["symbol"] == "BTCTMN"
    assert intent["stop_distance_pct"] == 0.9


def test_decision_agent_fallback_on_llm_exception():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = TimeoutError("LLM call timed out after 10s")

    agent = DecisionAgent(llm_client=mock_llm)
    candidate_context = {
        "symbol": "BTCTMN",
        "cycle_id": "cyc-51",
        "features": {},
        "spread_bps": 20.0,
        "evidence_ids": ["snap-1"],
        "has_open_position": False,
    }

    # Must cleanly fallback to NO_TRADE without crashing
    intent = agent.decide(candidate_context)
    assert intent["action"] == "NO_TRADE"
    assert intent["reason_code"] == "DATA_UNCERTAIN"
    assert "timed out" in intent["decision_rationale"]


def test_decision_agent_fallback_on_position_review_is_hold():
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("API rate limited")

    agent = DecisionAgent(llm_client=mock_llm)
    position_context = {
        "symbol": "BTCTMN",
        "cycle_id": "cyc-52",
        "features": {},
        "spread_bps": 20.0,
        "evidence_ids": ["snap-pos-1"],
        "has_open_position": True,  # Has open position!
    }

    # For existing positions, fallback must be HOLD (not closing position blindly)
    intent = agent.decide(position_context)
    assert intent["action"] == "HOLD"
    assert intent["reason_code"] == "DATA_UNCERTAIN"


def test_decision_agent_fallback_on_invalid_hallucinated_evidence():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "contract_version": "1.0",
        "decision_id": "dec-101",
        "cycle_id": "cyc-53",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Breakout",
        "invalidation_condition": "Drop",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["hallucinated-evidence-99"],  # Invalid evidence ID!
    }

    agent = DecisionAgent(llm_client=mock_llm)
    candidate_context = {
        "symbol": "BTCTMN",
        "cycle_id": "cyc-53",
        "features": {},
        "spread_bps": 20.0,
        "evidence_ids": ["valid-snap-1"],
        "has_open_position": False,
    }

    intent = agent.decide(candidate_context)
    assert intent["action"] == "NO_TRADE"
    assert intent["reason_code"] == "DATA_UNCERTAIN"

import pytest
import sys
from wallex_agent.domain.types import (
    TradeIntent,
    RiskDecision,
    MarketInfo,
    MarketSnapshot,
    Candidate,
    OrderRecord,
    PositionRecord,
    TradeRecord,
)
from wallex_agent.domain.validation import (
    validate_trade_intent,
    validate_market_info,
    validate_risk_decision,
    validate_order_record,
    validate_position_record,
    validate_trade_record,
    ValidationError,
)


def test_no_pydantic_in_domain_modules():
    # Strict project rule: No Pydantic models imported or used in domain layer
    import wallex_agent.domain.types as types_mod
    import wallex_agent.domain.validation as val_mod

    assert "pydantic" not in sys.modules or not any(
        "pydantic" in str(getattr(val, "__module__", ""))
        for val in types_mod.__dict__.values()
    ), "Domain types must not declare or use Pydantic models"


def test_valid_buy_trade_intent_passes_validation():
    intent: TradeIntent = {
        "contract_version": "1.0",
        "decision_id": "dec-001",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "High relative volume and positive breakout on 1m/5m",
        "invalidation_condition": "Price drops below recent 5m swing low",
        "stop_distance_pct": 1.2,
        "take_profit_distance_pct": 2.4,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["snap-1", "feat-1"],
    }
    context_evidence = {"snap-1", "feat-1", "extra-1"}
    validated = validate_trade_intent(intent, allowed_evidence_ids=context_evidence)
    assert validated["action"] == "BUY"
    assert validated["symbol"] == "BTCTMN"


def test_buy_trade_intent_missing_stop_distance_raises_error():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-002",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Drop below low",
        "stop_distance_pct": None,  # Invalid for BUY!
        "take_profit_distance_pct": None,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["snap-1"],
    }
    with pytest.raises(ValidationError, match="stop_distance_pct"):
        validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})


def test_invalid_action_rejected():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-003",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "SHORT",  # Forbidden in Spot!
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Short signal",
        "invalidation_condition": "",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["snap-1"],
    }
    with pytest.raises(ValidationError, match="action"):
        validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})


def test_unauthorized_evidence_id_rejected():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-004",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Invalidate",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["hallucinated-evidence-99"],
    }
    with pytest.raises(ValidationError, match="evidence_ids"):
        validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})


def test_valid_no_trade_intent():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-005",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "NO_TRADE",
        "strategy_id": None,
        "horizon_profile": None,
        "confidence": 0.2,
        "reason_code": "EDGE_INSUFFICIENT",
        "decision_rationale": "Spread is too wide and volume is dropping",
        "invalidation_condition": None,
        "stop_distance_pct": None,
        "take_profit_distance_pct": None,
        "max_holding_minutes": None,
        "parameter_overrides": {},
        "evidence_ids": ["snap-1"],
    }
    validated = validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})
    assert validated["action"] == "NO_TRADE"
    assert validated["strategy_id"] is None


def test_parameter_overrides_with_unknown_key_rejected():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-006",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Invalidate",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {"unknown_leverage": 10},
        "evidence_ids": ["snap-1"],
    }
    with pytest.raises(ValidationError, match="parameter_overrides"):
        validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})


def test_parameter_overrides_with_invalid_negative_value_rejected():
    intent = {
        "contract_version": "1.0",
        "decision_id": "dec-007",
        "cycle_id": "cyc-001",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Invalidate",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {"stop_distance_pct": -2.0},
        "evidence_ids": ["snap-1"],
    }
    with pytest.raises(ValidationError, match="parameter_overrides"):
        validate_trade_intent(intent, allowed_evidence_ids={"snap-1"})


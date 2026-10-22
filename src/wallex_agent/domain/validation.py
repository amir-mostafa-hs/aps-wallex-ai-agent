"""Pure Python semantic validation for domain types.

Strict constraint: Zero Pydantic models.
"""
from __future__ import annotations
from typing import Any, Mapping, Sequence, Set
from wallex_agent.domain.types import (
    TradeIntent,
    MarketInfo,
    RiskDecision,
    OrderRecord,
    PositionRecord,
    TradeRecord,
    Action,
    StrategyId,
    HorizonProfile,
    ReasonCode,
)


class ValidationError(ValueError):
    """Raised when domain object validation fails."""
    pass


VALID_ACTIONS: Set[str] = {"NO_TRADE", "BUY", "HOLD", "EXIT"}
VALID_STRATEGIES: Set[str] = {"momentum", "trend_following", "mean_reversion"}
VALID_HORIZONS: Set[str] = {"FAST", "INTRADAY_SHORT", "INTRADAY"}
VALID_REASONS: Set[str] = {
    "EDGE_INSUFFICIENT",
    "SIGNAL_VALID",
    "SIGNAL_INVALIDATED",
    "RISK_CONTEXT",
    "DATA_UNCERTAIN",
    "OTHER",
}


def validate_trade_intent(
    raw: Mapping[str, Any],
    allowed_evidence_ids: Sequence[str] | Set[str] | None = None,
) -> TradeIntent:
    """Semantically validates a TradeIntent dictionary in pure Python."""
    if not isinstance(raw, Mapping):
        raise ValidationError(f"TradeIntent must be a mapping, got {type(raw).__name__}")

    symbol = str(raw.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValidationError("TradeIntent 'symbol' must be a non-empty string.")

    action = raw.get("action")
    if action not in VALID_ACTIONS:
        raise ValidationError(f"Invalid TradeIntent 'action': {action}. Allowed: {sorted(VALID_ACTIONS)}")

    confidence = raw.get("confidence")
    if confidence is None or not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        raise ValidationError(f"TradeIntent 'confidence' must be float between 0.0 and 1.0, got {confidence}")

    reason_code = raw.get("reason_code")
    if reason_code not in VALID_REASONS:
        raise ValidationError(f"Invalid 'reason_code': {reason_code}")

    rationale = raw.get("decision_rationale")
    if not rationale or not str(rationale).strip():
        raise ValidationError("TradeIntent 'decision_rationale' must be a non-empty string.")

    evidence_ids = raw.get("evidence_ids")
    if not isinstance(evidence_ids, Sequence):
        raise ValidationError(f"TradeIntent 'evidence_ids' must be a sequence, got {type(evidence_ids).__name__}")
    
    if allowed_evidence_ids is not None:
        allowed_set = set(allowed_evidence_ids)
        for ev_id in evidence_ids:
            if ev_id not in allowed_set:
                raise ValidationError(f"Unauthorized 'evidence_ids' entry: {ev_id}. Not in context.")

    strategy_id = raw.get("strategy_id")
    horizon_profile = raw.get("horizon_profile")
    stop_distance_pct = raw.get("stop_distance_pct")
    take_profit_distance_pct = raw.get("take_profit_distance_pct")
    max_holding_minutes = raw.get("max_holding_minutes")
    invalidation_condition = raw.get("invalidation_condition")

    if action == "BUY":
        if strategy_id not in VALID_STRATEGIES:
            raise ValidationError(f"Action BUY requires valid strategy_id, got {strategy_id}")
        if horizon_profile not in VALID_HORIZONS:
            raise ValidationError(f"Action BUY requires valid horizon_profile, got {horizon_profile}")
        if stop_distance_pct is None or not isinstance(stop_distance_pct, (int, float)) or stop_distance_pct <= 0:
            raise ValidationError(f"Action BUY requires positive stop_distance_pct, got {stop_distance_pct}")
        if take_profit_distance_pct is not None:
            if not isinstance(take_profit_distance_pct, (int, float)) or take_profit_distance_pct <= 0:
                raise ValidationError(f"take_profit_distance_pct must be positive if provided, got {take_profit_distance_pct}")
        if max_holding_minutes is None or not isinstance(max_holding_minutes, int) or max_holding_minutes <= 0:
            raise ValidationError(f"Action BUY requires positive integer max_holding_minutes, got {max_holding_minutes}")
        if not invalidation_condition or not str(invalidation_condition).strip():
            raise ValidationError("Action BUY requires non-empty invalidation_condition.")

    raw_overrides = raw.get("parameter_overrides", {})
    if not isinstance(raw_overrides, Mapping):
        raise ValidationError("parameter_overrides must be a mapping/dict")

    allowed_override_keys = {"stop_distance_pct", "take_profit_distance_pct", "max_holding_minutes"}
    validated_overrides: dict[str, Any] = {}
    for k, v in raw_overrides.items():
        if k not in allowed_override_keys:
            raise ValidationError(f"Invalid parameter_overrides key '{k}'. Allowed keys: {allowed_override_keys}")
        if not isinstance(v, (int, float)) or v <= 0:
            raise ValidationError(f"Invalid parameter_overrides value for '{k}': must be a positive number (got {v})")
        validated_overrides[k] = float(v) if "pct" in k else int(v)

    return {
        "contract_version": str(raw.get("contract_version", "1.0")),
        "decision_id": str(raw.get("decision_id", "")),
        "cycle_id": str(raw.get("cycle_id", "")),
        "symbol": symbol,
        "action": action,  # type: ignore
        "strategy_id": strategy_id,  # type: ignore
        "horizon_profile": horizon_profile,  # type: ignore
        "confidence": float(confidence),
        "reason_code": reason_code,  # type: ignore
        "decision_rationale": str(rationale).strip(),
        "invalidation_condition": str(invalidation_condition).strip() if invalidation_condition else None,
        "stop_distance_pct": float(stop_distance_pct) if stop_distance_pct is not None else None,
        "take_profit_distance_pct": float(take_profit_distance_pct) if take_profit_distance_pct is not None else None,
        "max_holding_minutes": int(max_holding_minutes) if max_holding_minutes is not None else None,
        "parameter_overrides": validated_overrides,
        "evidence_ids": [str(eid) for eid in evidence_ids],
    }


def validate_market_info(raw: Mapping[str, Any]) -> MarketInfo:
    if not raw.get("symbol"):
        raise ValidationError("MarketInfo missing symbol")
    return {
        "symbol": str(raw["symbol"]).strip().upper(),
        "base_asset": str(raw.get("base_asset", "")).strip().upper(),
        "quote_asset": str(raw.get("quote_asset", "")).strip().upper(),
        "is_spot": bool(raw.get("is_spot", False)),
        "is_active": bool(raw.get("is_active", False)),
        "is_tmn_based": bool(raw.get("is_tmn_based", False)),
        "is_usdt_based": bool(raw.get("is_usdt_based", False)),
        "amount_precision": int(raw.get("amount_precision", 0)),
        "price_precision": int(raw.get("price_precision", 0)),
        "min_quantity": float(raw["min_quantity"]) if raw.get("min_quantity") is not None else None,
        "min_notional": float(raw["min_notional"]) if raw.get("min_notional") is not None else None,
    }


def validate_risk_decision(raw: Mapping[str, Any]) -> RiskDecision:
    return {
        "approved": bool(raw.get("approved", False)),
        "intent_id": str(raw.get("intent_id", "")),
        "symbol": str(raw.get("symbol", "")).upper(),
        "action": raw.get("action", "NO_TRADE"),  # type: ignore
        "approved_quantity": float(raw.get("approved_quantity", 0.0)),
        "approved_notional": float(raw.get("approved_notional", 0.0)),
        "projected_stop_price": float(raw["projected_stop_price"]) if raw.get("projected_stop_price") is not None else None,
        "projected_take_profit_price": float(raw["projected_take_profit_price"]) if raw.get("projected_take_profit_price") is not None else None,
        "reject_code": raw.get("reject_code"),
        "rejection_reason": str(raw["rejection_reason"]) if raw.get("rejection_reason") else None,
    }


def validate_order_record(raw: Mapping[str, Any]) -> OrderRecord:
    if not raw.get("client_id"):
        raise ValidationError("OrderRecord missing client_id")
    return {
        "client_id": str(raw["client_id"]),
        "exchange_order_id": str(raw["exchange_order_id"]) if raw.get("exchange_order_id") else None,
        "symbol": str(raw.get("symbol", "")).upper(),
        "side": raw.get("side", "BUY"),  # type: ignore
        "order_type": raw.get("order_type", "LIMIT"),  # type: ignore
        "price": float(raw["price"]) if raw.get("price") is not None else None,
        "quantity": float(raw.get("quantity", 0.0)),
        "status": raw.get("status", "CREATED"),  # type: ignore
        "executed_qty": float(raw.get("executed_qty", 0.0)),
        "executed_sum": float(raw.get("executed_sum", 0.0)),
        "cumulative_fee": float(raw.get("cumulative_fee", 0.0)),
        "created_at": float(raw.get("created_at", 0.0)),
        "updated_at": float(raw.get("updated_at", 0.0)),
        "fills": list(raw.get("fills", [])),
    }


def validate_position_record(raw: Mapping[str, Any]) -> PositionRecord:
    return {
        "position_id": str(raw.get("position_id", "")),
        "symbol": str(raw.get("symbol", "")).upper(),
        "quantity": float(raw.get("quantity", 0.0)),
        "entry_price": float(raw.get("entry_price", 0.0)),
        "current_price": float(raw.get("current_price", 0.0)),
        "unrealized_pnl_tmn": float(raw.get("unrealized_pnl_tmn", 0.0)),
        "realized_pnl_tmn": float(raw.get("realized_pnl_tmn", 0.0)),
        "cumulative_fee_tmn": float(raw.get("cumulative_fee_tmn", 0.0)),
        "stop_price": float(raw.get("stop_price", 0.0)),
        "take_profit_price": float(raw["take_profit_price"]) if raw.get("take_profit_price") is not None else None,
        "opened_at": float(raw.get("opened_at", 0.0)),
        "max_holding_seconds": float(raw.get("max_holding_seconds", 0.0)),
        "is_open": bool(raw.get("is_open", True)),
    }


def validate_trade_record(raw: Mapping[str, Any]) -> TradeRecord:
    return {
        "trade_id": str(raw.get("trade_id", "")),
        "symbol": str(raw.get("symbol", "")).upper(),
        "strategy_id": raw.get("strategy_id"),
        "horizon_profile": raw.get("horizon_profile"),
        "entry_price": float(raw.get("entry_price", 0.0)),
        "exit_price": float(raw.get("exit_price", 0.0)),
        "quantity": float(raw.get("quantity", 0.0)),
        "net_realized_pnl_tmn": float(raw.get("net_realized_pnl_tmn", 0.0)),
        "gross_realized_pnl_tmn": float(raw.get("gross_realized_pnl_tmn", 0.0)),
        "total_fee_tmn": float(raw.get("total_fee_tmn", 0.0)),
        "holding_seconds": float(raw.get("holding_seconds", 0.0)),
        "opened_at": float(raw.get("opened_at", 0.0)),
        "closed_at": float(raw.get("closed_at", 0.0)),
        "exit_reason": str(raw.get("exit_reason", "")),
        "loss_cause": raw.get("loss_cause"),
        "post_mortem_notes": str(raw["post_mortem_notes"]) if raw.get("post_mortem_notes") else None,
    }

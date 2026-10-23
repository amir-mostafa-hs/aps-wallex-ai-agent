"""High-velocity momentum strategy for Wallex Opportunity Agent.

Enforces:
1. Spot long-only.
2. Positive price acceleration over recent window.
3. Volume expansion (relative volume > 1.0).
4. Anti-averaging down (max 1 position per symbol).
5. Spread tolerance check.
"""
from __future__ import annotations
import uuid
from typing import Sequence
from wallex_agent.domain.types import Candle, TradeIntent


def evaluate_momentum_setup(
    candles_1m: Sequence[Candle],
    spread_bps: float,
    has_open_position: bool,
    symbol: str = "BTCTMN",
    cycle_id: str = "cyc-01",
    decision_id: str | None = None,
    evidence_ids: Sequence[str] | None = None,
    max_spread_bps: float = 40.0,
    momentum_window: int = 5,
    min_momentum_return_pct: float = 0.10,
    min_relative_volume: float = 1.0,
    default_stop_pct: float = 1.0,
    default_take_profit_pct: float = 2.0,
    default_max_holding_minutes: int = 8,
) -> TradeIntent:
    dec_id = decision_id or f"dec-{uuid.uuid4().hex[:8]}"
    ev_ids = list(evidence_ids or ["candlestick_momentum_setup"])

    if has_open_position:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "momentum",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "RISK_CONTEXT",
            "decision_rationale": "Symbol already has open position; anti-averaging down enforced.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    if spread_bps > max_spread_bps:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "momentum",
            "horizon_profile": None,
            "confidence": 0.95,
            "reason_code": "SPREAD_EXCESSIVE",
            "decision_rationale": f"Spread {spread_bps:.1f} bps exceeds limit {max_spread_bps:.1f} bps.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    if len(candles_1m) < momentum_window + 5:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "momentum",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "DATA_INSUFFICIENT",
            "decision_rationale": f"Insufficient 1m candles for momentum evaluation (need >= {momentum_window+5}).",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    recent_candles = candles_1m[-momentum_window:]
    past_candle = candles_1m[-momentum_window]
    curr_candle = candles_1m[-1]

    past_price = float(past_candle["close"])
    curr_price = float(curr_candle["close"])
    if past_price <= 0.0:
        ret_pct = 0.0
    else:
        ret_pct = ((curr_price - past_price) / past_price) * 100.0

    avg_vol = sum(float(c.get("volume", 0.0)) for c in candles_1m[-20:]) / max(1, len(candles_1m[-20:]))
    curr_vol = float(curr_candle.get("volume", 0.0))
    rvol = curr_vol / avg_vol if avg_vol > 0.0 else 1.0

    is_green = curr_price > float(curr_candle.get("open", curr_price))

    if ret_pct >= min_momentum_return_pct and rvol >= min_relative_volume and is_green:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "BUY",
            "strategy_id": "momentum",
            "horizon_profile": "FAST",
            "confidence": 0.82,
            "reason_code": "MOMENTUM_CONFIRMED",
            "decision_rationale": f"High momentum surge detected: {momentum_window}m return={ret_pct:.2f}%, rvol={rvol:.2f}.",
            "invalidation_condition": "Momentum exhaustion / reversal candle close below breakout base.",
            "stop_distance_pct": default_stop_pct,
            "take_profit_distance_pct": default_take_profit_pct,
            "max_holding_minutes": default_max_holding_minutes,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    return {
        "contract_version": "1.0",
        "decision_id": dec_id,
        "cycle_id": cycle_id,
        "symbol": symbol,
        "action": "NO_TRADE",
        "strategy_id": "momentum",
        "horizon_profile": None,
        "confidence": 0.80,
        "reason_code": "MOMENTUM_ABSENT",
        "decision_rationale": f"Momentum criteria not met (ret={ret_pct:.2f}%, rvol={rvol:.2f}, green={is_green}).",
        "invalidation_condition": None,
        "stop_distance_pct": None,
        "take_profit_distance_pct": None,
        "max_holding_minutes": None,
        "parameter_overrides": {},
        "evidence_ids": ev_ids,
    }

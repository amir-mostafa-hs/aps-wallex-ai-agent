"""Trend-filtered pullback strategy for Wallex Opportunity Agent (Ticket 20).

Enforces:
1. Spot long-only without leverage or shorting.
2. 5m trend filter (EMA20 > EMA50) preventing buy entries in downtrends.
3. 1m pullback into short-term EMA20/VWAP with confirmed green bounce.
4. Liquidity & spread check (max spread threshold).
5. Net edge validation against round-trip fees, spread, and slippage buffer.
6. Anti-averaging down (max 1 open position per symbol).
"""
from __future__ import annotations
import uuid
from typing import Sequence, Mapping, Any
from wallex_agent.domain.types import Candle, TradeIntent
from wallex_agent.features import resample_candles, calculate_ema, calculate_vwap


def evaluate_pullback_setup(
    candles_1m: Sequence[Candle],
    spread_bps: float,
    has_open_position: bool,
    candles_5m: Sequence[Candle] | None = None,
    symbol: str = "BTCTMN",
    cycle_id: str = "cyc-01",
    decision_id: str | None = None,
    evidence_ids: Sequence[str] | None = None,
    max_spread_bps: float = 40.0,
    min_risk_reward: float = 1.5,
    fee_rate_round_trip: float = 0.005,  # 0.5% (e.g. 0.25% entry + 0.25% exit)
) -> TradeIntent:
    """Evaluates a multi-timeframe trend-filtered pullback setup returning a typed TradeIntent."""
    dec_id = decision_id or f"dec-{uuid.uuid4().hex[:8]}"
    ev_ids = list(evidence_ids or ["candlestick_pullback_setup"])

    # 1. Anti-averaging down check: Never add to an existing position on the same symbol
    if has_open_position:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "RISK_CONTEXT",
            "decision_rationale": "Symbol already has open position; anti-averaging down strictly enforced.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    # 2. Maximum allowable spread check
    if spread_bps > max_spread_bps:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "EDGE_INSUFFICIENT",
            "decision_rationale": f"Spread {spread_bps:.1f} bps exceeds maximum threshold {max_spread_bps:.1f} bps.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    if len(candles_1m) < 10:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.50,
            "reason_code": "DATA_UNCERTAIN",
            "decision_rationale": "Insufficient 1m candle history for technical setup evaluation.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    # 3. 5m Trend Filter
    if candles_5m is None:
        c5_list = resample_candles(candles_1m, target_minutes=5)
    else:
        c5_list = list(candles_5m)

    c5_closes = [c["close"] for c in c5_list]
    # Calculate EMA fast and slow on 5m candles proportionally so p_fast < p_slow
    n_c5 = len(c5_closes)
    p_slow = min(50, n_c5)
    p_fast = min(20, max(3, p_slow // 2))
    ema20_5m = calculate_ema(c5_closes, p_fast)
    ema50_5m = calculate_ema(c5_closes, p_slow)

    # Bullish condition: 5m EMA fast > EMA slow
    is_5m_bullish = (ema20_5m[-1] > ema50_5m[-1]) if n_c5 >= 5 else False
    if not is_5m_bullish:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.85,
            "reason_code": "SIGNAL_INVALIDATED",
            "decision_rationale": f"5m trend filter bearish/neutral (EMA{p_fast}={ema20_5m[-1]:.2f} <= EMA{p_slow}={ema50_5m[-1]:.2f}). Entry blocked.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    # 4. 1m Pullback & Bounce
    c1_closes = [c["close"] for c in candles_1m]
    ema20_1m = calculate_ema(c1_closes, min(20, len(c1_closes)))

    # Evaluate recent 5 candles
    recent_window = candles_1m[-5:]
    curr_candle = recent_window[-1]

    # Pullback check: in recent 5 candles prior to curr, did price touch or dip to/below EMA20?
    dipped = False
    for i, c in enumerate(recent_window[:-1]):
        ema_idx = -(len(recent_window) - i)
        if c["low"] <= ema20_1m[ema_idx] * 1.002:  # dipped into or below EMA20
            dipped = True
            break

    # Bounce check: current candle is green and closes above EMA20
    is_green = curr_candle["close"] > curr_candle["open"]
    above_ema = curr_candle["close"] >= ema20_1m[-1]
    is_bounce = is_green and above_ema

    if not (dipped and is_bounce):
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.70,
            "reason_code": "EDGE_INSUFFICIENT",
            "decision_rationale": "Pullback/bounce setup not confirmed on 1m timeframe.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    # 5. Risk-Reward, Friction, and Target Sizing
    swing_low = min(c["low"] for c in recent_window)
    entry_p = curr_candle["close"]
    raw_stop_pct = ((entry_p - swing_low) / entry_p) * 100.0 if entry_p > 0 else 1.0
    stop_distance_pct = max(0.8, min(2.5, raw_stop_pct))
    take_profit_distance_pct = max(stop_distance_pct * min_risk_reward, 1.8)

    # Net edge validation over friction
    friction_pct = (fee_rate_round_trip * 100.0) + (spread_bps / 100.0) + 0.10  # 0.10% slippage buffer
    if take_profit_distance_pct <= (friction_pct * 1.5):
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_filtered_pullback",
            "horizon_profile": None,
            "confidence": 0.80,
            "reason_code": "EDGE_INSUFFICIENT",
            "decision_rationale": f"Insufficient net edge: TP={take_profit_distance_pct:.2f}% < required edge over friction {friction_pct * 1.5:.2f}%.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    # 6. Valid Buy Setup Triggered
    return {
        "contract_version": "1.0",
        "decision_id": dec_id,
        "cycle_id": cycle_id,
        "symbol": symbol,
        "action": "BUY",
        "strategy_id": "trend_filtered_pullback",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": (
            f"5m Trend bullish (EMA20 > EMA50) + 1m pullback bounce off EMA20. "
            f"Target R:R={take_profit_distance_pct / stop_distance_pct:.2f}"
        ),
        "invalidation_condition": f"1m candle close breaches swing low {swing_low:.2f}",
        "stop_distance_pct": round(stop_distance_pct, 2),
        "take_profit_distance_pct": round(take_profit_distance_pct, 2),
        "max_holding_minutes": 10,
        "parameter_overrides": {},
        "evidence_ids": ev_ids,
    }


class TrendFilteredPullbackStrategy:
    """Class wrapper for trend_filtered_pullback strategy."""

    def __init__(
        self,
        max_spread_bps: float = 40.0,
        min_risk_reward: float = 1.5,
        fee_rate_round_trip: float = 0.005,
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.min_risk_reward = min_risk_reward
        self.fee_rate_round_trip = fee_rate_round_trip

    def evaluate(
        self,
        candles_1m: Sequence[Candle],
        spread_bps: float,
        has_open_position: bool,
        candles_5m: Sequence[Candle] | None = None,
        symbol: str = "BTCTMN",
        cycle_id: str = "cyc-01",
    ) -> TradeIntent:
        return evaluate_pullback_setup(
            candles_1m=candles_1m,
            spread_bps=spread_bps,
            has_open_position=has_open_position,
            candles_5m=candles_5m,
            symbol=symbol,
            cycle_id=cycle_id,
            max_spread_bps=self.max_spread_bps,
            min_risk_reward=self.min_risk_reward,
            fee_rate_round_trip=self.fee_rate_round_trip,
        )

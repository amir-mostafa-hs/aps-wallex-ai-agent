"""Trend-following strategy for Wallex Opportunity Agent.

Enforces:
1. Spot long-only.
2. Moving average alignment (EMA20 > EMA50, price > EMA20).
3. Bullish continuation confirmation.
4. Anti-averaging down.
5. Spread tolerance check.
"""
from __future__ import annotations
import uuid
from typing import Sequence
from wallex_agent.domain.types import Candle, TradeIntent
from wallex_agent.features import calculate_ema


def evaluate_trend_following_setup(
    candles_1m: Sequence[Candle],
    spread_bps: float,
    has_open_position: bool,
    symbol: str = "BTCTMN",
    cycle_id: str = "cyc-01",
    decision_id: str | None = None,
    evidence_ids: Sequence[str] | None = None,
    max_spread_bps: float = 40.0,
    default_stop_pct: float = 1.2,
    default_take_profit_pct: float = 2.4,
    default_max_holding_minutes: int = 15,
) -> TradeIntent:
    dec_id = decision_id or f"dec-{uuid.uuid4().hex[:8]}"
    ev_ids = list(evidence_ids or ["candlestick_trend_following_setup"])

    if has_open_position:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_following",
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
            "strategy_id": "trend_following",
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

    if len(candles_1m) < 55:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_following",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "DATA_INSUFFICIENT",
            "decision_rationale": "Insufficient candles for trend following (need >= 55).",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    closes = [float(c["close"]) for c in candles_1m]
    ema20 = calculate_ema(closes, period=20)
    ema50 = calculate_ema(closes, period=50)

    if not ema20 or not ema50:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "NO_TRADE",
            "strategy_id": "trend_following",
            "horizon_profile": None,
            "confidence": 0.90,
            "reason_code": "DATA_INSUFFICIENT",
            "decision_rationale": "Insufficient EMA series length.",
            "invalidation_condition": None,
            "stop_distance_pct": None,
            "take_profit_distance_pct": None,
            "max_holding_minutes": None,
            "parameter_overrides": {},
            "evidence_ids": ev_ids,
        }

    ema20_val = ema20[-1]
    ema50_val = ema50[-1]

    curr_candle = candles_1m[-1]
    curr_close = float(curr_candle["close"])
    curr_open = float(curr_candle.get("open", curr_close))

    # Trend alignment: EMA20 > EMA50, price > EMA20, and current candle is green
    if ema20_val > ema50_val and curr_close > ema20_val and curr_close > curr_open:
        return {
            "contract_version": "1.0",
            "decision_id": dec_id,
            "cycle_id": cycle_id,
            "symbol": symbol,
            "action": "BUY",
            "strategy_id": "trend_following",
            "horizon_profile": "SWING_INTRADAY",
            "confidence": 0.85,
            "reason_code": "TREND_ALIGNED",
            "decision_rationale": f"Bullish trend confirmed: EMA20 ({ema20_val:.0f}) > EMA50 ({ema50_val:.0f}), price ({curr_close:.0f}) leading.",
            "invalidation_condition": "Candle close below EMA20 indicates trend breakdown.",
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
        "strategy_id": "trend_following",
        "horizon_profile": None,
        "confidence": 0.80,
        "reason_code": "TREND_NOT_ALIGNED",
        "decision_rationale": f"Trend not bullishly aligned (EMA20={ema20_val:.0f}, EMA50={ema50_val:.0f}, price={curr_close:.0f}).",
        "invalidation_condition": None,
        "stop_distance_pct": None,
        "take_profit_distance_pct": None,
        "max_holding_minutes": None,
        "parameter_overrides": {},
        "evidence_ids": ev_ids,
    }

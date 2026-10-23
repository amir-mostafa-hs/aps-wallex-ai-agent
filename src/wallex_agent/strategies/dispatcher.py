"""Authoritative multi-strategy dispatcher for Wallex Opportunity Agent."""
from __future__ import annotations
from typing import Sequence
from wallex_agent.domain.types import Candle, TradeIntent
from wallex_agent.strategies.trend_filtered_pullback import evaluate_pullback_setup
from wallex_agent.strategies.momentum import evaluate_momentum_setup
from wallex_agent.strategies.trend_following import evaluate_trend_following_setup


def dispatch_strategy_setup(
    strategy_id: str,
    candles_1m: Sequence[Candle],
    spread_bps: float,
    has_open_position: bool,
    symbol: str = "BTCTMN",
    cycle_id: str = "cyc-01",
    stop_distance_pct: float | None = None,
    take_profit_distance_pct: float | None = None,
    max_holding_minutes: int | None = None,
) -> TradeIntent:
    strat = strategy_id.strip().lower()

    if strat == "trend_filtered_pullback":
        intent = evaluate_pullback_setup(
            candles_1m=candles_1m,
            spread_bps=spread_bps,
            has_open_position=has_open_position,
            symbol=symbol,
            cycle_id=cycle_id,
        )
    elif strat == "momentum":
        intent = evaluate_momentum_setup(
            candles_1m=candles_1m,
            spread_bps=spread_bps,
            has_open_position=has_open_position,
            symbol=symbol,
            cycle_id=cycle_id,
            default_stop_pct=stop_distance_pct or 1.0,
            default_take_profit_pct=take_profit_distance_pct or 2.0,
            default_max_holding_minutes=max_holding_minutes or 8,
        )
    elif strat == "trend_following":
        intent = evaluate_trend_following_setup(
            candles_1m=candles_1m,
            spread_bps=spread_bps,
            has_open_position=has_open_position,
            symbol=symbol,
            cycle_id=cycle_id,
            default_stop_pct=stop_distance_pct or 1.2,
            default_take_profit_pct=take_profit_distance_pct or 2.4,
            default_max_holding_minutes=max_holding_minutes or 15,
        )
    elif strat == "mean_reversion":
        # Safe fallback for mean reversion to momentum with inverted trigger or safe no-trade
        intent = evaluate_momentum_setup(
            candles_1m=candles_1m,
            spread_bps=spread_bps,
            has_open_position=has_open_position,
            symbol=symbol,
            cycle_id=cycle_id,
            default_stop_pct=stop_distance_pct or 1.0,
            default_take_profit_pct=take_profit_distance_pct or 2.0,
            default_max_holding_minutes=max_holding_minutes or 8,
        )
        intent["strategy_id"] = "mean_reversion"
    else:
        raise ValueError(f"Unknown strategy_id '{strategy_id}'. Must be one of: trend_filtered_pullback, momentum, trend_following, mean_reversion.")

    if intent.get("action") == "BUY":
        if stop_distance_pct is not None:
            intent["stop_distance_pct"] = stop_distance_pct
        if take_profit_distance_pct is not None:
            intent["take_profit_distance_pct"] = take_profit_distance_pct
        if max_holding_minutes is not None:
            intent["max_holding_minutes"] = max_holding_minutes

    return intent

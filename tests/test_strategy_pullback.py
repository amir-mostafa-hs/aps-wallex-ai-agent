"""Tests for trend_filtered_pullback strategy (Ticket 20)."""
import pytest
from wallex_agent.domain.types import Candle, TradeIntent
from wallex_agent.features import resample_candles
from wallex_agent.strategies.trend_filtered_pullback import (
    evaluate_pullback_setup,
    TrendFilteredPullbackStrategy,
)
from wallex_agent.decision_agent import DecisionAgent


def _generate_synthetic_candles(base_price: float, trend_pct: float, count: int) -> list[Candle]:
    """Generates synthetic 1m candles with a defined drift."""
    candles: list[Candle] = []
    p = base_price
    start_ts = 1700000000
    for i in range(count):
        p = p * (1.0 + trend_pct / 100.0)
        c: Candle = {
            "timestamp": start_ts + i * 60,
            "open": p * 0.999,
            "high": p * 1.002,
            "low": p * 0.998,
            "close": p,
            "volume": 100.0,
        }
        candles.append(c)
    return candles


def test_strategy_blocks_buy_when_5m_trend_is_bearish():
    # 5m downtrend: prices steadily falling
    candles_1m = _generate_synthetic_candles(base_price=100000.0, trend_pct=-0.2, count=150)
    intent = evaluate_pullback_setup(
        candles_1m=candles_1m,
        spread_bps=10.0,
        has_open_position=False,
        symbol="BTCTMN",
        cycle_id="c-01",
    )
    assert intent["action"] == "NO_TRADE"
    assert "bearish" in intent["decision_rationale"].lower() or "trend" in intent["decision_rationale"].lower()


def test_strategy_blocks_buy_when_spread_is_too_wide():
    # Uptrend, but spread is 60 bps (> max allowed 40 bps)
    candles_1m = _generate_synthetic_candles(base_price=100000.0, trend_pct=0.1, count=150)
    intent = evaluate_pullback_setup(
        candles_1m=candles_1m,
        spread_bps=60.0,
        has_open_position=False,
        symbol="BTCTMN",
        cycle_id="c-02",
        max_spread_bps=40.0,
    )
    assert intent["action"] == "NO_TRADE"
    assert "spread" in intent["decision_rationale"].lower()


def test_strategy_blocks_averaging_down_if_already_holding_position():
    candles_1m = _generate_synthetic_candles(base_price=100000.0, trend_pct=0.1, count=150)
    intent = evaluate_pullback_setup(
        candles_1m=candles_1m,
        spread_bps=10.0,
        has_open_position=True,  # Already holding position
        symbol="BTCTMN",
        cycle_id="c-03",
    )
    assert intent["action"] in ("NO_TRADE", "HOLD")
    assert "position" in intent["decision_rationale"].lower() or "anti-averaging" in intent["decision_rationale"].lower()


def test_strategy_triggers_buy_on_confirmed_bullish_pullback():
    # 1. Base uptrend for 140 candles (establishes bullish 5m EMA20 > EMA50)
    candles_1m = _generate_synthetic_candles(base_price=100000.0, trend_pct=0.08, count=140)

    # 2. Add 3 pullback candles dipping into EMA
    last_p = candles_1m[-1]["close"]
    for i in range(3):
        last_p *= 0.997  # dip
        candles_1m.append({
            "timestamp": candles_1m[-1]["timestamp"] + 60,
            "open": last_p * 1.001,
            "high": last_p * 1.002,
            "low": last_p * 0.996,
            "close": last_p,
            "volume": 80.0,
        })

    # 3. Add strong bounce candle (close > open, closes back up)
    last_p *= 1.006
    candles_1m.append({
        "timestamp": candles_1m[-1]["timestamp"] + 60,
        "open": last_p * 0.995,
        "high": last_p * 1.003,
        "low": last_p * 0.994,
        "close": last_p,
        "volume": 250.0,  # volume expansion on bounce
    })

    intent = evaluate_pullback_setup(
        candles_1m=candles_1m,
        spread_bps=12.0,
        has_open_position=False,
        symbol="BTCTMN",
        cycle_id="c-04",
    )

    assert intent["action"] == "BUY"
    assert intent["strategy_id"] == "trend_filtered_pullback"
    assert intent["stop_distance_pct"] is not None and intent["stop_distance_pct"] > 0
    assert intent["take_profit_distance_pct"] is not None
    # R:R must be at least 1.5x
    assert intent["take_profit_distance_pct"] >= intent["stop_distance_pct"] * 1.49


def test_decision_agent_uses_trend_filtered_pullback_by_default():
    agent = DecisionAgent(heuristic_mode=True)
    assert agent.default_strategy == "trend_filtered_pullback"

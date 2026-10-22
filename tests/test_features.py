import pytest
from wallex_agent.domain.types import Candle
from wallex_agent.features import (
    parse_udf_history,
    resample_candles,
    compute_technical_features,
    calculate_spread_bps,
    calculate_depth_imbalance,
    is_data_stale,
)


def test_parse_udf_history():
    raw_udf = {
        "s": "ok",
        "t": [1700000000, 1700000060],
        "o": ["100.0", "102.0"],
        "h": ["105.0", "106.0"],
        "l": ["99.0", "101.0"],
        "c": ["102.0", "104.0"],
        "v": ["10.5", "15.2"],
    }
    candles = parse_udf_history(raw_udf)
    assert len(candles) == 2
    assert candles[0]["timestamp"] == 1700000000
    assert candles[0]["open"] == 100.0
    assert candles[0]["high"] == 105.0
    assert candles[0]["low"] == 99.0
    assert candles[0]["close"] == 102.0
    assert candles[0]["volume"] == 10.5

    # Test no data response
    assert parse_udf_history({"s": "no_data"}) == []


def test_resample_candles_1m_to_5m():
    # 5 one-minute candles starting at a 5-minute aligned timestamp
    base_ts = 1700000100 - (1700000100 % 300)  # aligned to 300s (5m)
    candles_1m: list[Candle] = [
        {"timestamp": base_ts + 0, "open": 100.0, "high": 105.0, "low": 98.0, "close": 102.0, "volume": 10.0},
        {"timestamp": base_ts + 60, "open": 102.0, "high": 108.0, "low": 101.0, "close": 107.0, "volume": 12.0},
        {"timestamp": base_ts + 120, "open": 107.0, "high": 109.0, "low": 106.0, "close": 108.0, "volume": 8.0},
        {"timestamp": base_ts + 180, "open": 108.0, "high": 110.0, "low": 105.0, "close": 106.0, "volume": 15.0},
        {"timestamp": base_ts + 240, "open": 106.0, "high": 107.0, "low": 103.0, "close": 105.0, "volume": 5.0},
    ]

    resampled = resample_candles(candles_1m, target_minutes=5)
    assert len(resampled) == 1
    c5 = resampled[0]
    assert c5["timestamp"] == base_ts
    assert c5["open"] == 100.0  # first open
    assert c5["high"] == 110.0  # max high
    assert c5["low"] == 98.0   # min low
    assert c5["close"] == 105.0 # last close
    assert c5["volume"] == 50.0 # sum volume (10+12+8+15+5)


def test_compute_technical_features():
    # Create 30 sequential candles
    candles: list[Candle] = []
    base_price = 100.0
    for i in range(30):
        price = base_price + i * 0.5
        candles.append({
            "timestamp": 1700000000 + i * 60,
            "open": price,
            "high": price + 1.0,
            "low": price - 0.5,
            "close": price + 0.5,
            "volume": 20.0 if i < 29 else 60.0,  # 3x volume surge on last candle
        })

    features = compute_technical_features(candles)
    assert "return_pct" in features
    assert "atr" in features
    assert "relative_volume" in features
    assert features["relative_volume"] > 2.0  # last volume is 60 vs avg ~20


def test_spread_and_depth_imbalance():
    # Bid 99, Ask 101, Mid = 100 -> Spread = (101 - 99)/100 * 10000 = 200 bps
    spread_bps = calculate_spread_bps(bid=99.0, ask=101.0)
    assert pytest.approx(spread_bps, rel=1e-3) == 200.0

    # Bid qty 30, Ask qty 10 -> imbalance = (30 - 10) / (30 + 10) = 0.5 (buy pressure)
    imbalance = calculate_depth_imbalance(total_bid_qty=30.0, total_ask_qty=10.0)
    assert pytest.approx(imbalance, rel=1e-3) == 0.5


def test_data_freshness():
    now = 1700000100.0
    # 40 seconds old snapshot is NOT stale (max_age=45)
    assert is_data_stale(timestamp=now - 40.0, current_time=now, max_age_seconds=45.0) is False
    # 50 seconds old snapshot IS stale (max_age=45)
    assert is_data_stale(timestamp=now - 50.0, current_time=now, max_age_seconds=45.0) is True

    # 4 seconds old execution quote is NOT stale (max_age=5)
    assert is_data_stale(timestamp=now - 4.0, current_time=now, max_age_seconds=5.0) is False
    # 6 seconds old execution quote IS stale (max_age=5)
    assert is_data_stale(timestamp=now - 6.0, current_time=now, max_age_seconds=5.0) is True

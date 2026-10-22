"""Market data parsing, candle resampling, and multi-timeframe feature engineering."""
from __future__ import annotations
import math
from typing import Any, Mapping, Sequence
from wallex_agent.domain.types import Candle


def parse_udf_history(udf_response: Mapping[str, Any]) -> list[Candle]:
    """Parses TradingView UDF format history from Wallex /v1/udf/history into a list of Candle."""
    status = udf_response.get("s")
    if status != "ok":
        return []

    timestamps = udf_response.get("t", [])
    opens = udf_response.get("o", [])
    highs = udf_response.get("h", [])
    lows = udf_response.get("l", [])
    closes = udf_response.get("c", [])
    volumes = udf_response.get("v", [])

    count = min(len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes))
    candles: list[Candle] = []
    for i in range(count):
        candles.append({
            "timestamp": int(timestamps[i]),
            "open": float(opens[i]),
            "high": float(highs[i]),
            "low": float(lows[i]),
            "close": float(closes[i]),
            "volume": float(volumes[i]),
        })
    return candles


def resample_candles(candles_1m: Sequence[Candle], target_minutes: int) -> list[Candle]:
    """Resamples 1-minute base candles into higher timeframes (e.g. 5m, 15m, 60m) without lookahead."""
    if not candles_1m or target_minutes <= 1:
        return list(candles_1m)

    interval_sec = target_minutes * 60
    buckets: dict[int, list[Candle]] = {}

    for c in candles_1m:
        bucket_ts = (c["timestamp"] // interval_sec) * interval_sec
        if bucket_ts not in buckets:
            buckets[bucket_ts] = []
        buckets[bucket_ts].append(c)

    resampled: list[Candle] = []
    for bucket_ts in sorted(buckets.keys()):
        group = buckets[bucket_ts]
        resampled.append({
            "timestamp": bucket_ts,
            "open": group[0]["open"],
            "high": max(c["high"] for c in group),
            "low": min(c["low"] for c in group),
            "close": group[-1]["close"],
            "volume": sum(c["volume"] for c in group),
        })
    return resampled


def calculate_spread_bps(bid: float, ask: float) -> float:
    """Calculates spread in basis points (1 bps = 0.01%)."""
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return 0.0
    return ((ask - bid) / mid) * 10000.0


def calculate_depth_imbalance(total_bid_qty: float, total_ask_qty: float) -> float:
    """Calculates order book depth imbalance bounded between -1.0 (all ask) and +1.0 (all bid)."""
    total = total_bid_qty + total_ask_qty
    if total <= 0:
        return 0.0
    return (total_bid_qty - total_ask_qty) / total


def is_data_stale(timestamp: float, current_time: float, max_age_seconds: float) -> bool:
    """Returns True if the time elapsed exceeds the maximum allowed age threshold."""
    return (current_time - timestamp) > max_age_seconds


def compute_technical_features(candles: Sequence[Candle]) -> dict[str, float]:
    """Computes technical indicator features from a sequence of candles."""
    if not candles:
        return {}

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]

    # Percentage return over the window
    return_pct = 0.0
    if len(closes) >= 2 and closes[0] > 0:
        return_pct = ((closes[-1] - closes[0]) / closes[0]) * 100.0

    # Average True Range (ATR)
    period = min(14, len(candles) - 1)
    atr = 0.0
    if period > 0:
        true_ranges: list[float] = []
        for i in range(1, len(candles)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)
        atr = sum(true_ranges[-period:]) / float(period)
    elif len(candles) == 1:
        atr = highs[0] - lows[0]

    # Relative volume (current candle vs previous N average)
    relative_volume = 1.0
    if len(volumes) >= 5:
        lookback = min(20, len(volumes) - 1)
        prior_avg = sum(volumes[-(lookback + 1):-1]) / float(lookback)
        if prior_avg > 0:
            relative_volume = volumes[-1] / prior_avg

    # Realized volatility (standard deviation of percentage returns)
    returns: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns.append(((closes[i] - closes[i - 1]) / closes[i - 1]) * 100.0)

    volatility = 0.0
    if len(returns) >= 2:
        mean_ret = sum(returns) / float(len(returns))
        variance = sum((r - mean_ret) ** 2 for r in returns) / float(len(returns) - 1)
        volatility = math.sqrt(variance)

    return {
        "return_pct": return_pct,
        "atr": atr,
        "relative_volume": relative_volume,
        "volatility": volatility,
        "latest_close": closes[-1],
        "latest_volume": volumes[-1],
    }

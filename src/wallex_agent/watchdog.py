"""Local Watchdog and emergency exit manager.

Operates with 100% independence from LLM decisions for rapid capital protection.
"""
from __future__ import annotations
from typing import TypedDict, Literal, Mapping, Sequence
from wallex_agent.domain.types import PositionRecord

TriggerType = Literal["STOP_LOSS", "TAKE_PROFIT", "TIME_EXPIRY", "EMERGENCY_FLATTEN"]


class WatchdogTrigger(TypedDict):
    trigger_type: TriggerType
    symbol: str
    position_id: str
    position_quantity: float
    trigger_price: float
    timestamp: float
    reason: str


class WatchdogHealthStatus(TypedDict):
    is_healthy: bool
    lag_seconds: float
    reason: str | None


class LocalWatchdog:
    """High-frequency price and position monitor enforcing deterministic exit rules."""

    def __init__(self, max_allowed_price_lag_seconds: float = 5.0) -> None:
        self.max_allowed_price_lag_seconds = max_allowed_price_lag_seconds

    def check_position(
        self,
        pos: PositionRecord,
        current_bid: float,
        current_time: float,
    ) -> WatchdogTrigger | None:
        """Evaluates a single position against the latest execution bid price and clock."""
        if not pos.get("is_open", True):
            return None

        symbol = pos["symbol"]
        pos_id = pos["position_id"]
        qty = pos["quantity"]

        # 1. Hard Stop-Loss breach check (priority 1)
        if current_bid <= pos["stop_price"]:
            return {
                "trigger_type": "STOP_LOSS",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": current_bid,
                "timestamp": current_time,
                "reason": f"Current bid {current_bid} breached hard stop-loss {pos['stop_price']}",
            }

        # 2. Take-Profit hit check
        tp_price = pos.get("take_profit_price")
        if tp_price is not None and current_bid >= tp_price:
            return {
                "trigger_type": "TAKE_PROFIT",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": current_bid,
                "timestamp": current_time,
                "reason": f"Current bid {current_bid} reached take-profit target {tp_price}",
            }

        # 3. Maximum holding duration expiry
        elapsed = current_time - pos["opened_at"]
        max_duration = pos["max_holding_seconds"]
        if elapsed >= max_duration:
            return {
                "trigger_type": "TIME_EXPIRY",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": current_bid,
                "timestamp": current_time,
                "reason": f"Position duration {elapsed:.1f}s exceeded max limit {max_duration:.1f}s",
            }

        return None

    def check_candle(
        self,
        pos: PositionRecord,
        candle: Mapping[str, Any],
        current_time: float | None = None,
    ) -> WatchdogTrigger | None:
        """Evaluates position against a complete price candle [low, high, close] with conservative stop-loss priority."""
        if not pos.get("is_open", True):
            return None

        symbol = pos["symbol"]
        pos_id = pos["position_id"]
        qty = pos["quantity"]

        candle_low = float(candle["low"])
        candle_high = float(candle["high"])
        candle_close = float(candle["close"])
        candle_open = float(candle.get("open", candle_close))
        ts = float(candle.get("timestamp", current_time if current_time is not None else 0.0))
        eval_time = current_time if current_time is not None else ts

        stop_price = float(pos["stop_price"])
        tp_price = float(pos["take_profit_price"]) if pos.get("take_profit_price") is not None else None

        sl_hit = candle_low <= stop_price
        tp_hit = (tp_price is not None) and (candle_high >= tp_price)

        # Conservative rule: If both SL and TP are touched in the same candle,
        # prioritize STOP_LOSS to prevent optimistic backtest overfitting.
        if sl_hit and tp_hit:
            exit_price = min(stop_price, candle_open)
            return {
                "trigger_type": "STOP_LOSS",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": exit_price,
                "timestamp": eval_time,
                "reason": (
                    f"Both SL ({stop_price}) and TP ({tp_price}) touched within candle "
                    f"range [{candle_low}, {candle_high}]. Conservative resolution triggered STOP_LOSS at {exit_price}"
                ),
            }

        if sl_hit:
            exit_price = min(stop_price, candle_open)
            return {
                "trigger_type": "STOP_LOSS",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": exit_price,
                "timestamp": eval_time,
                "reason": f"Candle low {candle_low} breached hard stop-loss {stop_price}",
            }

        if tp_hit and tp_price is not None:
            exit_price = max(tp_price, candle_open)
            return {
                "trigger_type": "TAKE_PROFIT",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": exit_price,
                "timestamp": eval_time,
                "reason": f"Candle high {candle_high} reached take-profit target {tp_price}",
            }

        # Check maximum holding duration expiry
        elapsed = eval_time - pos["opened_at"]
        max_duration = pos["max_holding_seconds"]
        if elapsed >= max_duration:
            return {
                "trigger_type": "TIME_EXPIRY",
                "symbol": symbol,
                "position_id": pos_id,
                "position_quantity": qty,
                "trigger_price": candle_close,
                "timestamp": eval_time,
                "reason": f"Position duration {elapsed:.1f}s exceeded max limit {max_duration:.1f}s",
            }

        return None

    def check_all(
        self,
        positions: Sequence[PositionRecord],
        prices: Mapping[str, float],
        current_time: float,
    ) -> list[WatchdogTrigger]:
        """Scans all open positions against a price feed dictionary."""
        triggers: list[WatchdogTrigger] = []
        for pos in positions:
            if not pos.get("is_open", True):
                continue
            symbol = pos["symbol"]
            bid = prices.get(symbol)
            if bid is None:
                continue

            trigger = self.check_position(pos, current_bid=bid, current_time=current_time)
            if trigger is not None:
                triggers.append(trigger)
        return triggers

    def evaluate_health(
        self,
        current_time: float,
        latest_price_timestamp: float,
    ) -> WatchdogHealthStatus:
        """Monitors watchdog data feed freshness to detect network or feed stagnation."""
        lag = current_time - latest_price_timestamp
        if lag > self.max_allowed_price_lag_seconds:
            return {
                "is_healthy": False,
                "lag_seconds": lag,
                "reason": "PRICE_STALE",
            }
        return {
            "is_healthy": True,
            "lag_seconds": lag,
            "reason": None,
        }

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

import pytest
from wallex_agent.domain.types import PositionRecord
from wallex_agent.watchdog import LocalWatchdog, WatchdogTrigger, WatchdogHealthStatus


def test_watchdog_detects_stop_loss_breach():
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-01",
        "symbol": "BTCTMN",
        "quantity": 0.05,
        "entry_price": 4000000.0,
        "current_price": 3950000.0,
        "unrealized_pnl_tmn": -2500.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 100.0,
        "stop_price": 3960000.0,  # Stop loss at 3,960,000
        "take_profit_price": 4100000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 300.0,  # 5 minutes
        "is_open": True,
    }

    # Bid is 3,950,000 <= stop 3,960,000 -> must trigger STOP_LOSS
    trigger = watchdog.check_position(pos, current_bid=3950000.0, current_time=1100.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "STOP_LOSS"
    assert trigger["symbol"] == "BTCTMN"
    assert trigger["position_quantity"] == 0.05
    assert trigger["trigger_price"] == 3950000.0


def test_watchdog_detects_take_profit_hit():
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-02",
        "symbol": "ETHTMN",
        "quantity": 1.2,
        "entry_price": 200000.0,
        "current_price": 215000.0,
        "unrealized_pnl_tmn": 18000.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 100.0,
        "stop_price": 195000.0,
        "take_profit_price": 210000.0,  # TP at 210,000
        "opened_at": 1000.0,
        "max_holding_seconds": 600.0,
        "is_open": True,
    }

    # Bid is 212,000 >= TP 210,000 -> must trigger TAKE_PROFIT
    trigger = watchdog.check_position(pos, current_bid=212000.0, current_time=1100.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "TAKE_PROFIT"
    assert trigger["symbol"] == "ETHTMN"


def test_watchdog_detects_max_holding_time_expiry():
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-03",
        "symbol": "SOLTMN",
        "quantity": 10.0,
        "entry_price": 10000.0,
        "current_price": 10050.0,
        "unrealized_pnl_tmn": 500.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 20.0,
        "stop_price": 9800.0,
        "take_profit_price": 10500.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 300.0,  # 5 minutes max
        "is_open": True,
    }

    # Price is between stop and TP, but 350 seconds have elapsed (exceeds 300s)
    trigger = watchdog.check_position(pos, current_bid=10020.0, current_time=1350.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "TIME_EXPIRY"
    assert trigger["symbol"] == "SOLTMN"


def test_watchdog_health_status_flags_price_lag():
    watchdog = LocalWatchdog(max_allowed_price_lag_seconds=5.0)

    # Price timestamp is 10 seconds older than current time -> lag alert!
    status = watchdog.evaluate_health(
        current_time=1000.0,
        latest_price_timestamp=990.0,
    )
    assert status["is_healthy"] is False
    assert status["reason"] == "PRICE_STALE"


def test_watchdog_candle_conservative_stop_when_both_limits_touched():
    # Ticket 19: When both SL and TP are touched in the same candle,
    # conservative anti-overfitting rule MUST trigger STOP_LOSS first.
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-both",
        "symbol": "BTCTMN",
        "quantity": 0.01,
        "entry_price": 4000000.0,
        "current_price": 4000000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 0.0,
        "stop_price": 3950000.0,      # SL at 3,950,000
        "take_profit_price": 4100000.0,  # TP at 4,100,000
        "opened_at": 1000.0,
        "max_holding_seconds": 600.0,
        "is_open": True,
    }

    # Candle range touches both: low 3,900,000 <= SL, high 4,150,000 >= TP
    candle = {
        "timestamp": 1100,
        "open": 4010000.0,
        "high": 4150000.0,
        "low": 3900000.0,
        "close": 4020000.0,
        "volume": 10.0,
    }

    trigger = watchdog.check_candle(pos, candle, current_time=1100.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "STOP_LOSS", "Conservative priority must resolve to STOP_LOSS"
    assert trigger["trigger_price"] == 3950000.0
    assert "Conservative" in trigger["reason"] or "Both SL and TP touched" in trigger["reason"]


def test_watchdog_candle_gap_down_stop_loss():
    # Ticket 19: Gap down opening below stop price should exit at open price (realistic slippage)
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-gap",
        "symbol": "BTCTMN",
        "quantity": 0.01,
        "entry_price": 4000000.0,
        "current_price": 4000000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 0.0,
        "stop_price": 3950000.0,
        "take_profit_price": 4100000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 600.0,
        "is_open": True,
    }

    candle = {
        "timestamp": 1100,
        "open": 3920000.0,  # Opened below SL (gap down)
        "high": 3940000.0,
        "low": 3900000.0,
        "close": 3910000.0,
        "volume": 5.0,
    }

    trigger = watchdog.check_candle(pos, candle, current_time=1100.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "STOP_LOSS"
    assert trigger["trigger_price"] == 3920000.0  # Slippage accounted: exited at candle open


def test_watchdog_candle_take_profit_hit():
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-tp",
        "symbol": "BTCTMN",
        "quantity": 0.01,
        "entry_price": 4000000.0,
        "current_price": 4000000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 0.0,
        "stop_price": 3950000.0,
        "take_profit_price": 4100000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 600.0,
        "is_open": True,
    }

    candle = {
        "timestamp": 1100,
        "open": 4020000.0,
        "high": 4120000.0,  # High >= TP 4,100,000
        "low": 4010000.0,
        "close": 4080000.0,
        "volume": 5.0,
    }

    trigger = watchdog.check_candle(pos, candle, current_time=1100.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "TAKE_PROFIT"
    assert trigger["trigger_price"] == 4100000.0


def test_watchdog_candle_time_expiry():
    watchdog = LocalWatchdog()

    pos: PositionRecord = {
        "position_id": "pos-time",
        "symbol": "BTCTMN",
        "quantity": 0.01,
        "entry_price": 4000000.0,
        "current_price": 4000000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 0.0,
        "stop_price": 3950000.0,
        "take_profit_price": 4100000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 300.0,
        "is_open": True,
    }

    candle = {
        "timestamp": 1400,  # Elapsed 400s > 300s
        "open": 4020000.0,
        "high": 4030000.0,
        "low": 4010000.0,
        "close": 4015000.0,
        "volume": 5.0,
    }

    trigger = watchdog.check_candle(pos, candle, current_time=1400.0)
    assert trigger is not None
    assert trigger["trigger_type"] == "TIME_EXPIRY"
    assert trigger["trigger_price"] == 4015000.0


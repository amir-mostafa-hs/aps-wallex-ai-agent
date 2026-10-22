import pytest
import sqlite3
from wallex_agent.telemetry import (
    TelemetryStore,
    calculate_trade_pnl,
    calculate_mtm_equity,
    classify_loss_cause,
)
from wallex_agent.domain.types import TradeRecord


def test_calculate_trade_pnl():
    # Buy 0.1 BTC at 4,000,000 TMN, Sell at 4,100,000 TMN
    # Gross P&L = (4,100,000 - 4,000,000) * 0.1 = 10,000 TMN
    # Fees: 1,000 TMN entry + 1,025 TMN exit = 2,025 TMN
    # Net P&L = 10,000 - 2,025 = 7,975 TMN
    gross, net = calculate_trade_pnl(
        entry_price=4000000.0,
        exit_price=4100000.0,
        quantity=0.1,
        entry_fee=1000.0,
        exit_fee=1025.0,
    )
    assert gross == 10000.0
    assert net == 7975.0


def test_calculate_mtm_equity():
    cash = 2500000.0
    positions = {
        "pos1": {"symbol": "BTCTMN", "quantity": 0.05, "entry_price": 4000000.0, "is_open": True},
        "pos2": {"symbol": "ETHTMN", "quantity": 1.0, "entry_price": 200000.0, "is_open": True},
    }
    bids = {
        "BTCTMN": 4100000.0,  # 0.05 * 4,100,000 = 205,000 TMN
        "ETHTMN": 195000.0,   # 1.0 * 195,000 = 195,000 TMN
    }

    total_equity, mtm_pnl = calculate_mtm_equity(cash=cash, positions=positions, current_bids=bids)
    # Total equity = 2.5M + 205k + 195k = 2,900,000 TMN
    assert total_equity == 2900000.0
    # MTM PnL = (205k - 200k) + (195k - 200k) = +5,000 - 5,000 = 0.0
    assert mtm_pnl == 0.0


def test_classify_loss_cause():
    # Trade exited via hard stop loss breach
    cause, notes = classify_loss_cause(
        exit_reason="STOP_LOSS_TRIGGERED",
        net_pnl=-5000.0,
        market_context={"stop_breached": True, "spread_bps": 20.0},
    )
    assert cause == "confirmed"
    assert "Stop-loss breach confirmed" in notes

    # Trade exited via timeout with high slippage
    cause, notes = classify_loss_cause(
        exit_reason="TIME_EXPIRY",
        net_pnl=-1200.0,
        market_context={"spread_bps": 120.0},
    )
    assert cause == "likely"

    # Trade exited with minimal loss and no clear anomaly
    cause, notes = classify_loss_cause(
        exit_reason="SIGNAL_INVALIDATED",
        net_pnl=-300.0,
        market_context={"spread_bps": 15.0},
    )
    assert cause == "unknown"


def test_telemetry_store_persists_events_and_trades():
    store = TelemetryStore(db_path=":memory:")
    store.initialize()

    # Log scanner cycle
    store.log_scanner_cycle(
        cycle_id="cyc-1",
        timestamp=1000.0,
        duration_ms=45.0,
        eligible_count=120,
        candidates=[{"symbol": "BTCTMN", "score": 15.0}],
    )

    # Log trade record
    trade: TradeRecord = {
        "trade_id": "tr-001",
        "symbol": "BTCTMN",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "entry_price": 4000000.0,
        "exit_price": 3950000.0,
        "quantity": 0.05,
        "gross_realized_pnl_tmn": -2500.0,
        "net_realized_pnl_tmn": -3500.0,
        "total_fee_tmn": 1000.0,
        "holding_seconds": 180.0,
        "opened_at": 1000.0,
        "closed_at": 1180.0,
        "exit_reason": "STOP_LOSS_TRIGGERED",
        "loss_cause": "confirmed",
        "post_mortem_notes": "Stop-loss breach confirmed",
    }
    store.log_trade(trade)

    trades = store.get_recent_trades(limit=10)
    assert len(trades) == 1
    assert trades[0]["trade_id"] == "tr-001"
    assert trades[0]["net_realized_pnl_tmn"] == -3500.0
    assert trades[0]["loss_cause"] == "confirmed"


def test_telemetry_store_equity_curve_and_fee_loss_ratio():
    store = TelemetryStore(db_path=":memory:")
    store.initialize()

    # Log equity snapshots
    store.log_equity_snapshot(timestamp=1000.0, total_equity=5000000.0, cash=5000000.0, open_positions_val=0.0, mtm_pnl=0.0)
    store.log_equity_snapshot(timestamp=1015.0, total_equity=4995000.0, cash=4500000.0, open_positions_val=495000.0, mtm_pnl=-5000.0)

    curve = store.get_equity_curve()
    assert len(curve) == 2
    assert curve[0]["total_equity"] == 5000000.0
    assert curve[1]["total_equity"] == 4995000.0

    # Log winning trade
    store.log_trade({
        "trade_id": "tr-win",
        "symbol": "BTCTMN",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "entry_price": 4000000.0,
        "exit_price": 4120000.0,
        "quantity": 0.1,
        "gross_realized_pnl_tmn": 12000.0,
        "net_realized_pnl_tmn": 10000.0,
        "total_fee_tmn": 2000.0,
        "holding_seconds": 120.0,
        "opened_at": 1000.0,
        "closed_at": 1120.0,
        "exit_reason": "TAKE_PROFIT",
        "loss_cause": None,
        "post_mortem_notes": "Target achieved",
    })

    # Log losing trade
    store.log_trade({
        "trade_id": "tr-loss",
        "symbol": "ETHTMN",
        "strategy_id": "trend_following",
        "horizon_profile": "FAST",
        "entry_price": 200000.0,
        "exit_price": 197000.0,
        "quantity": 1.0,
        "gross_realized_pnl_tmn": -3000.0,
        "net_realized_pnl_tmn": -4000.0,
        "total_fee_tmn": 1000.0,
        "holding_seconds": 60.0,
        "opened_at": 1130.0,
        "closed_at": 1190.0,
        "exit_reason": "STOP_LOSS",
        "loss_cause": "confirmed",
        "post_mortem_notes": "Adverse momentum breach",
    })

    summary = store.get_performance_summary()
    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["total_loss_tmn"] == 4000.0
    assert summary["fee_loss_ratio_pct"] == pytest.approx(25.0)


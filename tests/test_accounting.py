"""Tests for wallex_agent.domain.accounting (Ticket 18: Financial units & Decimal accounting)."""
from decimal import Decimal
import pytest
from wallex_agent.domain.accounting import (
    to_decimal,
    quantize_tmn,
    quantize_qty,
    compute_trade_pnl,
    calculate_mtm_equity_decimal,
    TradeFinancials,
)


def test_to_decimal_conversion():
    assert to_decimal(100) == Decimal("100")
    assert to_decimal("4500000000") == Decimal("4500000000")
    assert to_decimal(0.000166) == Decimal("0.000166")
    assert to_decimal(Decimal("123.45")) == Decimal("123.45")


def test_quantize_tmn():
    # Integer TMN quantization
    val = Decimal("14940.6789")
    assert quantize_tmn(val, precision=0) == Decimal("14941")
    assert quantize_tmn(val, precision=2) == Decimal("14940.68")
    assert quantize_tmn("5000000.00") == Decimal("5000000")


def test_quantize_qty_uses_round_down_for_exchange_safety():
    # Downward rounding ensures we do not submit orders exceeding balance
    qty = Decimal("0.000166789")
    assert quantize_qty(qty, precision=6) == Decimal("0.000166")
    assert quantize_qty(qty, precision=8) == Decimal("0.00016678")


def test_compute_trade_pnl_btc_real_scale():
    # Real market scenario: 0.000166 BTC at 4,500,000,000 TMN
    entry_price = Decimal("4500000000")
    exit_price = Decimal("4590000000")  # +2% TP
    quantity = Decimal("0.000166")
    entry_notional = entry_price * quantity  # 747,000 TMN
    exit_notional = exit_price * quantity    # 761,940 TMN

    fee_rate = Decimal("0.0025")  # 0.25%
    entry_fee = entry_notional * fee_rate   # 1,867.50 TMN
    exit_fee = exit_notional * fee_rate     # 1,904.85 TMN

    financials: TradeFinancials = compute_trade_pnl(
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
    )

    assert financials["gross_pnl"] == Decimal("14940")  # (4590M - 4500M) * 0.000166 = 90M * 0.000166
    assert financials["total_fee"] == Decimal("3772.35")
    assert financials["net_pnl"] == Decimal("11167.65")
    assert financials["entry_notional"] == Decimal("747000")
    assert financials["exit_notional"] == Decimal("761940")
    # Return % = 11167.65 / 747000 * 100 = 1.495%
    assert round(float(financials["return_pct"]), 3) == 1.495


def test_compute_trade_pnl_stop_loss_scenario():
    # Real market scenario: 0.000166 BTC at 4,500,000,000 TMN with -1.5% SL
    entry_price = Decimal("4500000000")
    exit_price = Decimal("4432500000")  # -1.5%
    quantity = Decimal("0.000166")
    entry_notional = entry_price * quantity  # 747,000 TMN
    exit_notional = exit_price * quantity    # 735,795 TMN

    fee_rate = Decimal("0.002")  # 0.2%
    entry_fee = entry_notional * fee_rate    # 1,494 TMN
    exit_fee = exit_notional * fee_rate      # 1,471.59 TMN

    financials = compute_trade_pnl(
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
    )

    expected_gross = (exit_price - entry_price) * quantity  # -67,500,000 * 0.000166 = -11,205
    assert financials["gross_pnl"] == Decimal("-11205")
    assert financials["total_fee"] == Decimal("2965.59")
    assert financials["net_pnl"] == Decimal("-14170.59")
    assert financials["return_pct"] < Decimal("0")


def test_calculate_mtm_equity_decimal():
    cash = Decimal("4000000")  # 4M TMN remaining cash from 5M credit
    positions = {
        "pos-1": {
            "symbol": "BTCTMN",
            "quantity": Decimal("0.0002"),
            "entry_price": Decimal("4500000000"),  # cost basis = 900,000 TMN
            "is_open": True,
        }
    }
    current_bids = {"BTCTMN": Decimal("4600000000")}  # current value = 920,000 TMN

    total_equity, unrealized_pnl = calculate_mtm_equity_decimal(cash, positions, current_bids)
    assert total_equity == Decimal("4920000")
    assert unrealized_pnl == Decimal("20000")

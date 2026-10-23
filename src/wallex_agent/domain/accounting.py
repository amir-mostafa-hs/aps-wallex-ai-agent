"""High-precision Decimal accounting and financial contracts for Wallex Opportunity Agent.

Strict constraint: Uses typing.TypedDict only. Zero Pydantic models.
All monetary values are denominated in Toman (TMN).
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from typing import TypedDict, Mapping, Any


def to_decimal(val: str | float | int | Decimal) -> Decimal:
    """Converts a scalar into Decimal safely, preventing float precision artifacts."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, float):
        # Convert via string representation to avoid 0.00016600000000000001
        return Decimal(str(val))
    return Decimal(str(val))


def quantize_tmn(
    amount: str | float | int | Decimal,
    precision: int = 0,
    rounding: str = ROUND_HALF_UP,
) -> Decimal:
    """Quantizes a TMN monetary amount to the specified decimal precision (default integer TMN)."""
    d = to_decimal(amount)
    if precision <= 0:
        step = Decimal("1")
    else:
        step = Decimal("10") ** -precision
    return d.quantize(step, rounding=rounding)


def quantize_qty(
    qty: str | float | int | Decimal,
    precision: int = 8,
    rounding: str = ROUND_DOWN,
) -> Decimal:
    """Quantizes asset quantity to the exchange precision using ROUND_DOWN for order safety."""
    d = to_decimal(qty)
    if precision <= 0:
        step = Decimal("1")
    else:
        step = Decimal("10") ** -precision
    return d.quantize(step, rounding=rounding)


class TradeFinancials(TypedDict):
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    entry_notional: Decimal
    exit_notional: Decimal
    entry_fee: Decimal
    exit_fee: Decimal
    total_fee: Decimal
    gross_pnl: Decimal
    net_pnl: Decimal
    return_pct: Decimal


def compute_trade_pnl(
    entry_price: str | float | int | Decimal,
    exit_price: str | float | int | Decimal,
    quantity: str | float | int | Decimal,
    entry_fee: str | float | int | Decimal = 0,
    exit_fee: str | float | int | Decimal = 0,
) -> TradeFinancials:
    """Computes exact gross and net P&L and return percentage using Decimal precision in TMN."""
    e_price = to_decimal(entry_price)
    x_price = to_decimal(exit_price)
    qty = to_decimal(quantity)
    e_fee = to_decimal(entry_fee)
    x_fee = to_decimal(exit_fee)

    entry_notional = e_price * qty
    exit_notional = x_price * qty
    gross_pnl = (x_price - e_price) * qty
    total_fee = e_fee + x_fee
    net_pnl = gross_pnl - total_fee

    if entry_notional > Decimal("0"):
        return_pct = (net_pnl / entry_notional) * Decimal("100")
    else:
        return_pct = Decimal("0")

    return {
        "entry_price": e_price,
        "exit_price": x_price,
        "quantity": qty,
        "entry_notional": entry_notional,
        "exit_notional": exit_notional,
        "entry_fee": e_fee,
        "exit_fee": x_fee,
        "total_fee": total_fee,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "return_pct": return_pct,
    }


def calculate_mtm_equity_decimal(
    cash: str | float | int | Decimal,
    positions: Mapping[str, Mapping[str, Any]],
    current_bids: Mapping[str, Any],
) -> tuple[Decimal, Decimal]:
    """Calculates Mark-to-Market Total Equity and Unrealized P&L in TMN using Decimal."""
    open_val = Decimal("0")
    cost_basis = Decimal("0")

    for pos in positions.values():
        if not pos.get("is_open", True):
            continue
        sym = str(pos["symbol"])
        qty = to_decimal(pos["quantity"])
        entry = to_decimal(pos["entry_price"])
        bid_raw = current_bids.get(sym, entry)
        bid = to_decimal(bid_raw)

        open_val += qty * bid
        cost_basis += qty * entry

    total_equity = to_decimal(cash) + open_val
    mtm_pnl = open_val - cost_basis
    return (total_equity, mtm_pnl)

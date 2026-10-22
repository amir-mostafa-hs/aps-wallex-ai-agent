"""Deterministic Portfolio Risk Engine and Capital Allocator."""
from __future__ import annotations
from typing import TypedDict, Mapping
from wallex_agent.domain.types import (
    TradeIntent,
    RiskDecision,
    PositionRecord,
    OrderRecord,
)


class PortfolioState(TypedDict):
    total_equity_tmn: float
    available_cash_tmn: float
    open_positions: Mapping[str, PositionRecord]
    open_orders: Mapping[str, OrderRecord]


class RiskEngine:
    """Zero-trust deterministic gatekeeper enforcing strict portfolio risk boundaries."""

    def __init__(
        self,
        risk_per_trade_equity_pct: float = 0.005,
        max_position_notional_equity_pct: float = 0.15,
        max_total_exposure_equity_pct: float = 0.40,
        min_cash_reserve_equity_pct: float = 0.50,
        max_open_positions: int = 3,
        min_notional_tmn: float = 100000.0,
        initial_capital_tmn: float = 5000000.0,
        liquidation_floor_tmn: float = 4500000.0,
        warning_limit_tmn: float = 4600000.0,
        maker_fee_rate: float = 0.002,
        taker_fee_rate: float = 0.0025,
        min_edge_multiplier: float = 1.0,
    ) -> None:
        self.risk_per_trade_equity_pct = risk_per_trade_equity_pct
        self.max_position_notional_equity_pct = max_position_notional_equity_pct
        self.max_total_exposure_equity_pct = max_total_exposure_equity_pct
        self.min_cash_reserve_equity_pct = min_cash_reserve_equity_pct
        self.max_open_positions = max_open_positions
        self.min_notional_tmn = min_notional_tmn
        self.initial_capital_tmn = initial_capital_tmn

        # Normalize liquidation floor: support ratio (0.90), per-mille (900.0), or exact TMN (4,500,000.0)
        if 0.0 < liquidation_floor_tmn <= 1.0:
            norm_liq_floor = liquidation_floor_tmn * initial_capital_tmn
        elif 1.0 < liquidation_floor_tmn <= 1000.0:
            norm_liq_floor = (liquidation_floor_tmn / 1000.0) * initial_capital_tmn
        else:
            norm_liq_floor = liquidation_floor_tmn

        # Normalize warning limit
        if 0.0 < warning_limit_tmn <= 1.0:
            norm_warn_limit = warning_limit_tmn * initial_capital_tmn
        elif 1.0 < warning_limit_tmn <= 1000.0:
            norm_warn_limit = (warning_limit_tmn / 1000.0) * initial_capital_tmn
        else:
            norm_warn_limit = warning_limit_tmn

        # If warning limit equals or exceeds initial capital (e.g. 1000 per-mille from Wallex API),
        # set a sensible 20% safety cushion between liquidation floor and baseline equity
        if norm_warn_limit >= initial_capital_tmn:
            norm_warn_limit = norm_liq_floor + (initial_capital_tmn - norm_liq_floor) * 0.2

        self.liquidation_floor_tmn = norm_liq_floor
        self.warning_limit_tmn = norm_warn_limit
        self.maker_fee_rate = maker_fee_rate
        self.taker_fee_rate = taker_fee_rate
        self.min_edge_multiplier = min_edge_multiplier

    def evaluate(
        self,
        intent: TradeIntent,
        portfolio: PortfolioState,
        current_price: float,
        spread_bps: float = 20.0,
    ) -> RiskDecision:
        """Evaluates a TradeIntent against portfolio state and market quote."""
        symbol = intent["symbol"]
        action = intent["action"]
        decision_id = intent["decision_id"]

        if action in ("NO_TRADE", "HOLD"):
            return {
                "approved": False,
                "intent_id": decision_id,
                "symbol": symbol,
                "action": action,
                "approved_quantity": 0.0,
                "approved_notional": 0.0,
                "projected_stop_price": None,
                "projected_take_profit_price": None,
                "reject_code": None,
                "rejection_reason": f"No action required for {action}",
            }

        if action == "EXIT":
            # Check if there is an active position for this symbol
            active_pos: PositionRecord | None = None
            for p in portfolio["open_positions"].values():
                if p["symbol"] == symbol and p.get("is_open", True):
                    active_pos = p
                    break

            if active_pos is None:
                return {
                    "approved": False,
                    "intent_id": decision_id,
                    "symbol": symbol,
                    "action": "EXIT",
                    "approved_quantity": 0.0,
                    "approved_notional": 0.0,
                    "projected_stop_price": None,
                    "projected_take_profit_price": None,
                    "reject_code": "POSITION_LIMIT",
                    "rejection_reason": f"No active position to exit for symbol {symbol}",
                }

            exit_qty = active_pos["quantity"]
            exit_notional = exit_qty * current_price
            return {
                "approved": True,
                "intent_id": decision_id,
                "symbol": symbol,
                "action": "EXIT",
                "approved_quantity": exit_qty,
                "approved_notional": exit_notional,
                "projected_stop_price": None,
                "projected_take_profit_price": None,
                "reject_code": None,
                "rejection_reason": None,
            }

        # BUY Action Validation
        total_equity = portfolio["total_equity_tmn"]
        available_cash = portfolio["available_cash_tmn"]

        # 1. Liquidation safety floor
        if total_equity <= self.warning_limit_tmn or total_equity <= self.liquidation_floor_tmn:
            return self._reject(decision_id, symbol, action, "LIQUIDATION_RISK", "Account equity approaching liquidation limit")

        # 2. Maximum concurrent open positions
        open_pos_count = len([p for p in portfolio["open_positions"].values() if p.get("is_open", True)])
        if open_pos_count >= self.max_open_positions:
            return self._reject(decision_id, symbol, action, "POSITION_LIMIT", f"Max open positions ({self.max_open_positions}) reached")

        # 3. Check existing position or open order on same symbol (avoid averaging down / duplicate orders)
        has_pos = any(p["symbol"] == symbol and p.get("is_open", True) for p in portfolio["open_positions"].values())
        has_order = any(o["symbol"] == symbol for o in portfolio["open_orders"].values())
        if has_pos or has_order:
            return self._reject(decision_id, symbol, action, "POSITION_LIMIT", f"Symbol {symbol} already has active position or open order")

        # 4. Sizing calculation
        stop_pct = intent["stop_distance_pct"]
        if stop_pct is None or stop_pct <= 0:
            return self._reject(decision_id, symbol, action, "INVALID_INTENT", "BUY intent missing valid stop_distance_pct")

        stop_dist_ratio = stop_pct / 100.0
        risk_budget = total_equity * self.risk_per_trade_equity_pct
        sized_notional = risk_budget / stop_dist_ratio
        max_notional = total_equity * self.max_position_notional_equity_pct
        approved_notional = min(sized_notional, max_notional)

        # 5. Min notional check
        if approved_notional < self.min_notional_tmn:
            return self._reject(
                decision_id,
                symbol,
                action,
                "UNVERIFIED_NOTIONAL",
                f"Sized notional {approved_notional:.1f} is below minimum {self.min_notional_tmn:.1f}",
            )

        # 6. Total exposure check
        current_exposure = sum(
            p["quantity"] * p["current_price"] for p in portfolio["open_positions"].values() if p.get("is_open", True)
        )
        if (current_exposure + approved_notional) / total_equity > self.max_total_exposure_equity_pct:
            return self._reject(decision_id, symbol, action, "EXPOSURE_CAP", "Total portfolio exposure cap breached")

        # 7. Cash reserve check
        remaining_cash = available_cash - approved_notional
        if remaining_cash / total_equity < self.min_cash_reserve_equity_pct:
            return self._reject(decision_id, symbol, action, "INSUFFICIENT_CASH", "Minimum cash reserve threshold breached")

        # 8. Friction vs expected edge
        friction_pct = (self.taker_fee_rate * 2 * 100.0) + (spread_bps / 100.0)
        required_edge = friction_pct * self.min_edge_multiplier
        expected_edge = intent["take_profit_distance_pct"] or (stop_pct * 1.5)
        if expected_edge < required_edge:
            return self._reject(
                decision_id,
                symbol,
                action,
                "EDGE_INSUFFICIENT",
                f"Expected edge {expected_edge:.2f}% does not meet required minimum {required_edge:.2f}% (friction {friction_pct:.2f}% x {self.min_edge_multiplier:.1f})",
            )

        if current_price <= 0:
            return self._reject(decision_id, symbol, action, "STALE_DATA", f"Invalid price {current_price}")

        approved_quantity = approved_notional / current_price
        projected_stop = current_price * (1.0 - stop_dist_ratio)
        projected_tp = (
            current_price * (1.0 + (intent["take_profit_distance_pct"] / 100.0))
            if intent["take_profit_distance_pct"]
            else None
        )

        return {
            "approved": True,
            "intent_id": decision_id,
            "symbol": symbol,
            "action": "BUY",
            "approved_quantity": approved_quantity,
            "approved_notional": approved_notional,
            "projected_stop_price": projected_stop,
            "projected_take_profit_price": projected_tp,
            "reject_code": None,
            "rejection_reason": None,
        }

    def _reject(
        self,
        decision_id: str,
        symbol: str,
        action: str,
        reject_code: str,
        reason: str,
    ) -> RiskDecision:
        return {
            "approved": False,
            "intent_id": decision_id,
            "symbol": symbol,
            "action": action,  # type: ignore
            "approved_quantity": 0.0,
            "approved_notional": 0.0,
            "projected_stop_price": None,
            "projected_take_profit_price": None,
            "reject_code": reject_code,  # type: ignore
            "rejection_reason": reason,
        }

"""Authoritative Order Executor, client-id idempotency, and reconciliation."""
from __future__ import annotations
import math
import time
import uuid
from typing import Any, Mapping
from wallex_agent.domain.types import (
    OrderRecord,
    OrderFill,
    RiskDecision,
    OrderSide,
    OrderStatus,
)
from wallex_agent.domain.validation import validate_order_record


class ExchangeExecutionError(Exception):
    """Raised when an order submission or reconciliation fails."""
    pass


def quantize_number(value: float, precision: int) -> float:
    """Quantizes a float to a given decimal precision using truncation to prevent over-allocation."""
    if precision <= 0:
        return float(math.floor(value))
    factor = 10.0 ** precision
    return math.floor(value * factor) / factor


class OrderExecutor:
    """The single authoritative executor communicating with exchange trading endpoints."""

    def __init__(self, exchange_client: Any) -> None:
        self.exchange_client = exchange_client
        self._open_orders: dict[str, OrderRecord] = {}

    def register_open_order(self, order: OrderRecord) -> None:
        """Tracks an open order in local state."""
        self._open_orders[order["client_id"]] = order

    def remove_open_order(self, client_id: str) -> None:
        """Removes a finalized/cancelled order from local active tracking."""
        self._open_orders.pop(client_id, None)

    def submit_order(
        self,
        decision: RiskDecision,
        price: float,
        price_precision: int,
        amount_precision: int,
    ) -> OrderRecord:
        """Quantizes, checks for self-trading, dispatches order, and handles timeouts via query."""
        if not decision.get("approved"):
            raise ExchangeExecutionError("Cannot submit an unapproved RiskDecision.")

        symbol = decision["symbol"]
        action = decision["action"]
        side: OrderSide = "BUY" if action == "BUY" else "SELL"

        # 1. Self-Trade Prevention: cancel any opposite open order on this symbol before submitting
        opposite_side: OrderSide = "SELL" if side == "BUY" else "BUY"
        conflicting = [
            o for o in self._open_orders.values()
            if o["symbol"] == symbol and o["side"] == opposite_side
        ]
        for conf in conflicting:
            try:
                res = self.exchange_client.cancel_order(conf["client_id"])
                if isinstance(res, Mapping) and res.get("success") is False:
                    raise ExchangeExecutionError(f"Failed to cancel opposing order {conf['client_id']}: {res}")
            except ExchangeExecutionError:
                raise
            except Exception as e:
                raise ExchangeExecutionError(f"Exception during opposing order cancellation for {conf['client_id']}: {e}")
            self.remove_open_order(conf["client_id"])

        # 2. Quantize quantity and price to exchange step/tick sizes
        qty = quantize_number(decision["approved_quantity"], amount_precision)
        limit_price = quantize_number(price, price_precision)
        client_id = f"wallex-{uuid.uuid4().hex[:12]}"
        now = time.time()

        order_record: OrderRecord = {
            "client_id": client_id,
            "exchange_order_id": None,
            "symbol": symbol,
            "side": side,
            "order_type": "LIMIT",
            "price": limit_price,
            "quantity": qty,
            "status": "CREATED",
            "executed_qty": 0.0,
            "executed_sum": 0.0,
            "cumulative_fee": 0.0,
            "created_at": now,
            "updated_at": now,
            "fills": [],
        }

        # 3. Dispatch to exchange API with timeout reconciliation
        try:
            resp = self.exchange_client.create_order(
                symbol=symbol,
                side=side,
                order_type="LIMIT",
                price=limit_price,
                quantity=qty,
                client_id=client_id,
            )
            result = resp.get("result", {})
            order_record["exchange_order_id"] = str(result.get("id", "")) if result.get("id") else None
            order_record["status"] = result.get("status", "SUBMITTED")
            order_record["executed_qty"] = float(result.get("executedQty", 0.0))
            order_record["executed_sum"] = float(result.get("executedSum", 0.0))
            order_record["cumulative_fee"] = float(result.get("fee", 0.0))
            order_record["updated_at"] = time.time()
            self.register_open_order(order_record)
            return order_record

        except Exception as exc:
            # NETWORK TIMEOUT OR RESET: Reconcile before retrying! Never send duplicate order blindly.
            try:
                reconciled = self.exchange_client.get_order(client_id)
                res = reconciled.get("result", {})
                if res:
                    order_record["exchange_order_id"] = str(res.get("id", ""))
                    order_record["status"] = res.get("status", "SUBMITTED")
                    order_record["updated_at"] = time.time()
                    self.register_open_order(order_record)
                    return order_record
            except Exception:
                pass

            order_record["status"] = "UNKNOWN"
            order_record["updated_at"] = time.time()
            return order_record

    def reconcile_update(
        self,
        order: OrderRecord,
        exchange_payload: Mapping[str, Any],
    ) -> OrderRecord:
        """Applies exchange status and fill updates to an internal OrderRecord."""
        order["status"] = exchange_payload.get("status", order["status"])
        order["executed_qty"] = float(exchange_payload.get("executedQty", order["executed_qty"]))
        order["executed_sum"] = float(exchange_payload.get("executedSum", order["executed_sum"]))
        order["cumulative_fee"] = float(exchange_payload.get("fee", order["cumulative_fee"]))
        order["updated_at"] = time.time()

        if order["status"] in ("FILLED", "CANCELLED", "REJECTED"):
            self.remove_open_order(order["client_id"])

        return order


class ShadowOrderExecutor:
    """Authoritative Shadow Order Executor that simulates order fills locally with zero exchange network access."""

    def __init__(self, taker_fee_rate: float = 0.0025, maker_fee_rate: float = 0.002) -> None:
        self.taker_fee_rate = taker_fee_rate
        self.maker_fee_rate = maker_fee_rate
        self._open_orders: dict[str, OrderRecord] = {}

    def register_open_order(self, order: OrderRecord) -> None:
        """Tracks an open order in local shadow state."""
        self._open_orders[order["client_id"]] = order

    def remove_open_order(self, client_id: str) -> None:
        """Removes a finalized/cancelled order from local active tracking."""
        self._open_orders.pop(client_id, None)

    def submit_order(
        self,
        decision: RiskDecision,
        price: float,
        price_precision: int,
        amount_precision: int,
    ) -> OrderRecord:
        """Simulates order execution locally with realistic fee quantization; makes ZERO network calls."""
        if not decision.get("approved"):
            raise ExchangeExecutionError("Cannot submit an unapproved RiskDecision.")

        symbol = decision["symbol"]
        action = decision["action"]
        side: OrderSide = "BUY" if action == "BUY" else "SELL"

        # 1. Self-Trade Prevention: cancel any opposite open order on this symbol
        opposite_side: OrderSide = "SELL" if side == "BUY" else "BUY"
        conflicting = [
            cid for cid, o in self._open_orders.items()
            if o["symbol"] == symbol and o["side"] == opposite_side
        ]
        for conf_cid in conflicting:
            self.remove_open_order(conf_cid)

        # 2. Quantize quantity and price to precision
        qty = quantize_number(decision["approved_quantity"], amount_precision)
        limit_price = quantize_number(price, price_precision)
        client_id = f"shadow-{uuid.uuid4().hex[:12]}"
        now = time.time()
        sum_quote = qty * limit_price
        fee = sum_quote * self.taker_fee_rate
        fee_asset = "TMN" if "TMN" in symbol else "USDT"

        fill: dict[str, Any] = {
            "fill_id": f"sfill-{uuid.uuid4().hex[:8]}",
            "price": limit_price,
            "quantity": qty,
            "sum_quote": sum_quote,
            "fee": fee,
            "fee_asset": fee_asset,
            "feeAsset": fee_asset,
            "timestamp": now,
        }

        order_record: OrderRecord = {
            "client_id": client_id,
            "exchange_order_id": f"sim-{uuid.uuid4().hex[:8]}",
            "symbol": symbol,
            "side": side,
            "order_type": "LIMIT",
            "price": limit_price,
            "quantity": qty,
            "status": "FILLED",
            "executed_qty": qty,
            "executed_sum": sum_quote,
            "cumulative_fee": fee,
            "created_at": now,
            "updated_at": now,
            "fills": [fill],  # type: ignore
        }
        return order_record

    def reconcile_update(
        self,
        order: OrderRecord,
        exchange_payload: Mapping[str, Any],
    ) -> OrderRecord:
        """No-op update for local shadow simulated state."""
        return order


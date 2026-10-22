import pytest
from unittest.mock import MagicMock
from wallex_agent.domain.types import OrderRecord, RiskDecision
from wallex_agent.executor import (
    OrderExecutor,
    quantize_number,
    ExchangeExecutionError,
)


def test_quantize_number():
    assert quantize_number(0.12345678, precision=4) == 0.1234
    assert quantize_number(1234567.89, precision=0) == 1234567.0
    assert quantize_number(55.555, precision=2) == 55.55


def test_order_executor_submits_quantized_order():
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "success": True,
        "result": {
            "id": 998877,
            "clientId": "test-cid-1",
            "status": "SUBMITTED",
            "executedQty": "0.0",
            "executedSum": "0.0",
        },
    }

    executor = OrderExecutor(exchange_client=mock_client)
    decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-1",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.123456789,
        "approved_notional": 500000.0,
        "projected_stop_price": 3900000.0,
        "projected_take_profit_price": 4200000.0,
        "reject_code": None,
        "rejection_reason": None,
    }

    order = executor.submit_order(
        decision=decision,
        price=4000000.88,
        price_precision=0,
        amount_precision=4,
    )

    assert order["status"] == "SUBMITTED"
    assert order["quantity"] == 0.1234  # Quantized to 4 decimals
    assert order["price"] == 4000000.0  # Quantized to 0 decimals with floor
    assert order["client_id"] != ""
    mock_client.create_order.assert_called_once()


def test_order_executor_reconciles_on_timeout_rather_than_blind_retry():
    mock_client = MagicMock()
    # First submit times out!
    mock_client.create_order.side_effect = TimeoutError("Network timeout during POST /orders")
    # Query by client_id discovers the order actually reached the exchange and was SUBMITTED!
    mock_client.get_order.return_value = {
        "success": True,
        "result": {
            "id": 12345,
            "clientId": "some-client-id",
            "status": "SUBMITTED",
            "executedQty": "0.0",
            "executedSum": "0.0",
        },
    }

    executor = OrderExecutor(exchange_client=mock_client)
    decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-2",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.05,
        "approved_notional": 200000.0,
        "projected_stop_price": None,
        "projected_take_profit_price": None,
        "reject_code": None,
        "rejection_reason": None,
    }

    # Should not raise exception and should reconcile order state
    order = executor.submit_order(decision=decision, price=4000000.0, price_precision=0, amount_precision=4)
    assert order["status"] == "SUBMITTED"
    # Verify blind retry was NOT attempted (create_order called only once!)
    assert mock_client.create_order.call_count == 1
    mock_client.get_order.assert_called_once()


def test_self_trade_prevention_cancels_opposing_orders_first():
    mock_client = MagicMock()
    mock_client.cancel_order.return_value = {"success": True}
    mock_client.create_order.return_value = {
        "success": True,
        "result": {"id": 222, "status": "SUBMITTED", "executedQty": "0.0", "executedSum": "0.0"},
    }

    executor = OrderExecutor(exchange_client=mock_client)
    # Register an active BUY open order on BTCTMN
    existing_order: OrderRecord = {
        "client_id": "open-buy-1",
        "exchange_order_id": "111",
        "symbol": "BTCTMN",
        "side": "BUY",
        "order_type": "LIMIT",
        "price": 3900000.0,
        "quantity": 0.05,
        "status": "SUBMITTED",
        "executed_qty": 0.0,
        "executed_sum": 0.0,
        "cumulative_fee": 0.0,
        "created_at": 100.0,
        "updated_at": 100.0,
        "fills": [],
    }
    executor.register_open_order(existing_order)

    # Now an EXIT (SELL) is ordered
    exit_decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-exit",
        "symbol": "BTCTMN",
        "action": "EXIT",
        "approved_quantity": 0.05,
        "approved_notional": 200000.0,
        "projected_stop_price": None,
        "projected_take_profit_price": None,
        "reject_code": None,
        "rejection_reason": None,
    }

    sell_order = executor.submit_order(exit_decision, price=4000000.0, price_precision=0, amount_precision=4)
    # Opposing BUY order must have been cancelled before submitting SELL!
    mock_client.cancel_order.assert_called_once_with("open-buy-1")
    assert sell_order["side"] == "SELL"

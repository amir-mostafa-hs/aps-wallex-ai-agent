import pytest
from unittest.mock import MagicMock
from wallex_agent.domain.types import RiskDecision
from wallex_agent.executor import (
    OrderExecutor,
    ShadowOrderExecutor,
    ExchangeExecutionError,
)
from wallex_agent.harness import SystemTradingHarness
from wallex_agent.universe import MarketUniverse
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine
from wallex_agent.telemetry import TelemetryStore


def test_shadow_order_executor_simulates_fill_without_network():
    executor = ShadowOrderExecutor(taker_fee_rate=0.0025)
    decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-1",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.005123,
        "approved_notional": 500000.0,
        "projected_stop_price": 95000000.0,
        "projected_take_profit_price": 105000000.0,
        "reject_code": None,
        "rejection_reason": None,
    }

    order = executor.submit_order(
        decision=decision,
        price=100000000.0,
        price_precision=0,
        amount_precision=6,
    )

    assert order["status"] == "FILLED"
    assert order["client_id"].startswith("shadow-")
    assert order["symbol"] == "BTCTMN"
    assert order["side"] == "BUY"
    assert order["quantity"] == 0.005123
    assert order["price"] == 100000000.0
    assert order["executed_qty"] == 0.005123
    assert order["executed_sum"] == pytest.approx(512300.0)
    assert order["cumulative_fee"] == pytest.approx(512300.0 * 0.0025)
    assert len(order["fills"]) == 1
    assert order["fills"][0]["feeAsset"] == "TMN"


def test_shadow_order_executor_rejects_unapproved_decision():
    executor = ShadowOrderExecutor()
    decision: RiskDecision = {
        "approved": False,
        "intent_id": "dec-rej",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.0,
        "approved_notional": 0.0,
        "projected_stop_price": None,
        "projected_take_profit_price": None,
        "reject_code": "EXCEEDS_EXPOSURE",
        "rejection_reason": "Exposure limit reached",
    }
    with pytest.raises(ExchangeExecutionError, match="Cannot submit an unapproved"):
        executor.submit_order(decision=decision, price=100000.0, price_precision=0, amount_precision=4)


def test_shadow_order_executor_prevents_self_trade():
    executor = ShadowOrderExecutor()
    buy_decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-buy",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.001,
        "approved_notional": 100000.0,
        "projected_stop_price": None,
        "projected_take_profit_price": None,
        "reject_code": None,
        "rejection_reason": None,
    }
    # Register an open SELL order
    executor.register_open_order({
        "client_id": "shadow-opposing-1",
        "exchange_order_id": None,
        "symbol": "BTCTMN",
        "side": "SELL",
        "order_type": "LIMIT",
        "price": 100000000.0,
        "quantity": 0.001,
        "status": "SUBMITTED",
        "executed_qty": 0.0,
        "executed_sum": 0.0,
        "cumulative_fee": 0.0,
        "created_at": 1000.0,
        "updated_at": 1000.0,
        "fills": [],
    })

    assert "shadow-opposing-1" in executor._open_orders
    executor.submit_order(decision=buy_decision, price=100000000.0, price_precision=0, amount_precision=4)
    # Opposing SELL order must have been cancelled / removed from open orders
    assert "shadow-opposing-1" not in executor._open_orders


def test_harness_in_shadow_mode_never_calls_live_exchange_client(tmp_path):
    mock_exchange_client = MagicMock()
    mock_exchange_client.create_order = MagicMock(side_effect=RuntimeError("LIVE ORDER DISPATCH FORBIDDEN IN SHADOW"))

    universe = MarketUniverse.build(
        markets=[
            {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0}
        ],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )
    db_file = str(tmp_path / "shadow_test.db")
    telemetry = TelemetryStore(db_path=db_file)
    telemetry.initialize()

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(heuristic_mode=True),
        risk_engine=RiskEngine(
            risk_per_trade_equity_pct=0.015,
            max_position_notional_equity_pct=0.20,
            min_notional_tmn=100000.0,
            liquidation_floor_tmn=1000000.0,
        ),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 100000000.0},
        exchange_client=mock_exchange_client,
    )

    # Verify harness.executor is strictly a ShadowOrderExecutor
    assert isinstance(harness.executor, ShadowOrderExecutor)

    # Force a buy decision and execute
    decision: RiskDecision = {
        "approved": True,
        "intent_id": "dec-force-1",
        "symbol": "BTCTMN",
        "action": "BUY",
        "approved_quantity": 0.005,
        "approved_notional": 500000.0,
        "projected_stop_price": 98000000.0,
        "projected_take_profit_price": 104000000.0,
        "reject_code": None,
        "rejection_reason": None,
    }

    order = harness.executor.submit_order(
        decision=decision,
        price=100000000.0,
        price_precision=0,
        amount_precision=4,
    )

    # Must succeed locally in shadow mode
    assert order["status"] == "FILLED"
    assert order["client_id"].startswith("shadow-")

    # The mock exchange client create_order MUST NEVER have been called
    mock_exchange_client.create_order.assert_not_called()
    mock_exchange_client.cancel_order.assert_not_called()

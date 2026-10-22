import pytest
from unittest.mock import MagicMock
from wallex_agent.harness import SystemTradingHarness, SimulatedExchangeAdapter
from wallex_agent.universe import MarketUniverse
from wallex_agent.scanner import CandidateScanner
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine
from wallex_agent.watchdog import LocalWatchdog
from wallex_agent.telemetry import TelemetryStore


def test_simulated_exchange_adapter_fills_orders():
    adapter = SimulatedExchangeAdapter(
        initial_prices={"BTCTMN": 4000000.0},
        maker_fee_rate=0.002,
        taker_fee_rate=0.0025,
    )
    # Submit a BUY order
    order_resp = adapter.create_order(
        symbol="BTCTMN",
        side="BUY",
        order_type="LIMIT",
        price=4000000.0,
        quantity=0.05,
        client_id="sim-client-1",
    )
    assert order_resp["success"] is True
    res = order_resp["result"]
    assert res["status"] == "FILLED"
    assert float(res["executedQty"]) == 0.05
    assert float(res["fee"]) == pytest.approx(4000000.0 * 0.05 * 0.0025)  # taker fee


def test_system_harness_end_to_end_cycle_in_shadow_mode():
    # Setup mock components
    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()

    universe = MarketUniverse.build(
        markets=[
            {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0}
        ],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "contract_version": "1.0",
        "decision_id": "dec-sim-1",
        "cycle_id": "cyc-1",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Strong volume momentum",
        "invalidation_condition": "Drop below low",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-btc-1"],
    }

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(llm_client=mock_llm),
        risk_engine=RiskEngine(
            risk_per_trade_equity_pct=0.005,
            max_position_notional_equity_pct=0.15,
            min_notional_tmn=100000.0,
        ),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4000000.0},
    )

    # Run cycle with a high-score candidate
    market_snapshot = {
        "BTCTMN": {
            "features": {"return_pct": 2.5, "relative_volume": 3.0, "volatility": 1.2, "latest_volume": 1000.0},
            "spread_bps": 20.0,
            "is_stale": False,
            "evidence_ids": ["ev-btc-1"],
            "current_price": 4000000.0,
        }
    }

    cycle_result = harness.run_cycle(market_snapshot, timestamp=1000.0)
    assert cycle_result["orders_submitted"] == 1
    assert "BTCTMN" in harness.portfolio["open_positions"]
    pos = harness.portfolio["open_positions"]["BTCTMN"]
    assert pos["is_open"] is True
    assert pos["entry_price"] == 4000000.0
    assert harness.portfolio["available_cash_tmn"] < 5000000.0


def test_system_harness_end_of_contest_liquidation():
    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()
    universe = MarketUniverse.build(
        markets=[{"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0}],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=4500000.0,
        universe=universe,
        decision_agent=DecisionAgent(llm_client=MagicMock()),
        risk_engine=RiskEngine(),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4200000.0},
    )

    # Manually seed an open position
    harness.portfolio["open_positions"]["BTCTMN"] = {
        "position_id": "pos-01",
        "symbol": "BTCTMN",
        "quantity": 0.1,
        "entry_price": 4000000.0,
        "current_price": 4200000.0,
        "unrealized_pnl_tmn": 20000.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 1000.0,
        "stop_price": 3900000.0,
        "take_profit_price": 4300000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 600.0,
        "is_open": True,
    }

    # Trigger end of contest liquidation
    flattened_orders = harness.liquidate_all_positions(reason="END_OF_CONTEST")
    assert len(flattened_orders) == 1
    assert flattened_orders[0]["side"] == "SELL"
    # Position must be closed and coin balance flattened into cash
    assert len(harness.portfolio["open_positions"]) == 0
    assert harness.portfolio["available_cash_tmn"] > 4500000.0


def test_harness_rejects_stale_execution_quote():
    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()
    universe = MarketUniverse.build(
        markets=[{"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0}],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = {
        "contract_version": "1.0",
        "decision_id": "dec-stale",
        "cycle_id": "cyc-1",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.85,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Momentum",
        "invalidation_condition": "Loss of momentum",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-1"],
    }
    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(llm_client=mock_llm),
        risk_engine=RiskEngine(),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4000000.0},
        max_execution_quote_age_seconds=5.0,
    )
    # Market snapshot with quote timestamp 10.0 seconds old (> 5.0s max age)
    market_snapshot = {
        "BTCTMN": {
            "features": {"return_pct": 2.5, "relative_volume": 3.0, "volatility": 1.2, "latest_volume": 1000.0},
            "spread_bps": 20.0,
            "is_stale": False,
            "evidence_ids": ["ev-1"],
            "current_price": 4000000.0,
            "quote_timestamp": 990.0,  # 10s before cycle time 1000.0
        }
    }
    cycle_result = harness.run_cycle(market_snapshot, timestamp=1000.0)
    assert cycle_result["orders_submitted"] == 0
    assert len(harness.portfolio["open_positions"]) == 0


def test_harness_prioritizes_open_position_review_via_priority_queue():
    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()
    universe = MarketUniverse.build(
        markets=[
            {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0},
            {"symbol": "ETHTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0},
        ],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )

    invoked_symbols = []

    def mock_decide(context):
        sym = context["symbol"]
        invoked_symbols.append(sym)
        if context.get("has_open_position"):
            return {
                "contract_version": "1.0",
                "decision_id": "dec-exit-eth",
                "cycle_id": "cyc-1",
                "symbol": sym,
                "action": "EXIT",
                "strategy_id": "momentum",
                "horizon_profile": "FAST",
                "confidence": 0.9,
                "reason_code": "SIGNAL_INVALIDATED",
                "decision_rationale": "Exit nearing limit",
                "invalidation_condition": "Time limit",
                "stop_distance_pct": None,
                "take_profit_distance_pct": None,
                "max_holding_minutes": None,
                "parameter_overrides": {},
                "evidence_ids": ["ev-eth-1"],
            }
        else:
            return {
                "contract_version": "1.0",
                "decision_id": "dec-buy-btc",
                "cycle_id": "cyc-1",
                "symbol": sym,
                "action": "BUY",
                "strategy_id": "momentum",
                "horizon_profile": "FAST",
                "confidence": 0.8,
                "reason_code": "SIGNAL_VALID",
                "decision_rationale": "Buy BTC candidate",
                "invalidation_condition": "Drop",
                "stop_distance_pct": 1.0,
                "take_profit_distance_pct": 2.0,
                "max_holding_minutes": 5,
                "parameter_overrides": {},
                "evidence_ids": ["ev-btc-1"],
            }

    mock_agent = MagicMock()
    mock_agent.decide.side_effect = mock_decide

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=mock_agent,
        risk_engine=RiskEngine(),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4000000.0, "ETHTMN": 2000000.0},
    )

    # Seed an active position in ETHTMN that has reached 80% of max holding time
    harness.portfolio["open_positions"]["ETHTMN"] = {
        "position_id": "pos-eth-01",
        "symbol": "ETHTMN",
        "quantity": 0.5,
        "entry_price": 2000000.0,
        "current_price": 2000000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 0.0,
        "stop_price": 1900000.0,
        "take_profit_price": 2100000.0,
        "opened_at": 1000.0,
        "max_holding_seconds": 300.0,  # 300 seconds
        "is_open": True,
    }

    # At timestamp 1250.0 (250s elapsed = 83% of holding time):
    # A candidate BTCTMN has a strong signal
    market_snapshot = {
        "ETHTMN": {
            "features": {"return_pct": 0.1, "relative_volume": 1.0, "volatility": 0.01, "latest_volume": 500.0},
            "spread_bps": 15.0,
            "is_stale": False,
            "evidence_ids": ["ev-eth-1"],
            "current_price": 2000000.0,
            "quote_timestamp": 1250.0,
        },
        "BTCTMN": {
            "features": {"return_pct": 3.0, "relative_volume": 4.0, "volatility": 0.02, "latest_volume": 2000.0},
            "spread_bps": 15.0,
            "is_stale": False,
            "evidence_ids": ["ev-btc-1"],
            "current_price": 4000000.0,
            "quote_timestamp": 1250.0,
        },
    }

    cycle_result = harness.run_cycle(market_snapshot, timestamp=1250.0)

    # ReviewPriorityQueue must evaluate ETHTMN first
    assert invoked_symbols[0] == "ETHTMN"
    # And ETHTMN position should now be exited
    assert "ETHTMN" not in harness.portfolio["open_positions"]



"""Tests for Historical Backtest Engine (Ticket 21: Zero Look-Ahead, Real Candles, Run IDs)."""
from decimal import Decimal
import pytest
from wallex_agent.domain.types import Candle
from wallex_agent.backtest_engine import HistoricalBacktestEngine, BacktestRunResult


def _build_test_candles(count: int = 150) -> list[Candle]:
    """Builds a realistic sequence of 1m candles for testing."""
    candles: list[Candle] = []
    base_ts = 1700000000
    price = 4500000000.0  # BTC TMN real scale

    for i in range(count):
        # 0 to 120: steady uptrend (+0.05% per candle)
        # 121 to 124: slight pullback (-0.2% per candle)
        # 125: strong green bounce (+0.4%)
        # 126 to 149: uptrend continues (+0.1% per candle)
        if i < 120:
            drift = 1.0005
        elif 120 <= i < 124:
            drift = 0.998
        elif i == 124:
            drift = 1.004
        else:
            drift = 1.001

        price *= drift
        candles.append({
            "timestamp": base_ts + i * 60,
            "open": price * 0.9995,
            "high": price * 1.001,
            "low": price * 0.999,
            "close": price,
            "volume": 2.5 if i != 124 else 8.0,
        })
    return candles


def test_backtest_engine_generates_unique_run_id():
    engine = HistoricalBacktestEngine(initial_capital_tmn=5000000.0)
    candles = _build_test_candles(60)

    res1 = engine.run(symbol="BTCTMN", candles_1m=candles, strategy_id="trend_filtered_pullback")
    res2 = engine.run(symbol="BTCTMN", candles_1m=candles, strategy_id="trend_filtered_pullback")

    assert res1["run_id"] != res2["run_id"]
    assert res1["run_id"].startswith("bt-")
    assert res2["run_id"].startswith("bt-")


def test_backtest_engine_zero_lookahead_guarantee():
    engine = HistoricalBacktestEngine(initial_capital_tmn=5000000.0)
    candles = _build_test_candles(80)

    inspected_lengths = []

    def mock_observer(current_step_candles: list[Candle], current_time: float):
        # Assert no future candles leak into the step
        assert current_step_candles[-1]["timestamp"] <= current_time
        inspected_lengths.append(len(current_step_candles))

    engine.run(
        symbol="BTCTMN",
        candles_1m=candles,
        step_callback=mock_observer,
        warmup_candles=30,
    )

    # Must increment strictly step by step
    assert len(inspected_lengths) == 50
    assert inspected_lengths == list(range(30, 80))


def test_backtest_engine_uses_decimal_accounting_and_exact_formula():
    engine = HistoricalBacktestEngine(initial_capital_tmn=5000000.0)
    candles = _build_test_candles(150)

    result: BacktestRunResult = engine.run(
        symbol="BTCTMN",
        candles_1m=candles,
        strategy_id="trend_filtered_pullback",
        stop_distance_pct=1.0,
        take_profit_distance_pct=2.0,
    )

    # Net PnL must exactly equal Gross PnL - Total Fees within rounding
    gross = Decimal(str(result["gross_pnl_tmn"]))
    fees = Decimal(str(result["total_fees_tmn"]))
    net = Decimal(str(result["net_pnl_tmn"]))

    assert round(net, 2) == round(gross - fees, 2)
    assert result["initial_capital_tmn"] == 5000000.0
    assert "trades" in result
    assert "summary" in result


def test_dashboard_backtest_endpoint_with_trend_filtered_pullback():
    from fastapi.testclient import TestClient
    from wallex_agent.dashboard import create_dashboard_app
    from wallex_agent.harness import SystemTradingHarness
    from wallex_agent.universe import MarketUniverse
    from wallex_agent.decision_agent import DecisionAgent
    from wallex_agent.risk_engine import RiskEngine
    from wallex_agent.telemetry import TelemetryStore

    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()
    universe = MarketUniverse.build(
        markets=[{"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 6, "price_precision": 0}],
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )
    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(heuristic_mode=True),
        risk_engine=RiskEngine(),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4500000000.0},
    )

    app = create_dashboard_app(harness, auth_token="secret-test-token")
    client = TestClient(app)

    resp = client.post(
        "/api/backtest/run",
        headers={"Authorization": "Bearer secret-test-token"},
        json={
            "strategy_id": "trend_filtered_pullback",
            "cycles": 40,
            "stop_distance_pct": 1.2,
            "take_profit_distance_pct": 2.2,
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "run_id" in data
    assert data["run_id"].startswith("bt-")
    assert data["strategy_id"] == "trend_filtered_pullback"
    assert "gross_pnl_tmn" in data
    assert "net_pnl_tmn" in data
    assert "total_fees_tmn" in data
    assert "trades" in data
    assert "equity_curve" in data
    assert len(data["equity_curve"]) > 0
    for pt in data["equity_curve"]:
        assert "timestamp" in pt
        assert "total_equity" in pt
        assert "equity_tmn" in pt
        assert pt["total_equity"] == pt["equity_tmn"]



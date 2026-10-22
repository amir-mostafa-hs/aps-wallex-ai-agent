"""Tests for Status Dashboard and Control Interface."""
from __future__ import annotations
import pytest
import time
from fastapi.testclient import TestClient

from wallex_agent.universe import MarketUniverse
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine
from wallex_agent.telemetry import TelemetryStore
from wallex_agent.harness import SystemTradingHarness
from wallex_agent.dashboard import create_dashboard_app


@pytest.fixture
def test_harness(tmp_path) -> SystemTradingHarness:
    raw_markets = [
        {"symbol": "USDTTMN", "base_asset": "USDT", "quote_asset": "TMN", "is_spot": True, "is_active": True, "amount_precision": 2, "price_precision": 0},
        {"symbol": "BTCTMN", "base_asset": "BTC", "quote_asset": "TMN", "is_spot": True, "is_active": True, "amount_precision": 6, "price_precision": 0},
    ]
    universe = MarketUniverse.build(
        markets=raw_markets,
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )
    decision_agent = DecisionAgent()
    risk_engine = RiskEngine()
    db_file = tmp_path / "telemetry.db"
    telemetry = TelemetryStore(str(db_file))

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=decision_agent,
        risk_engine=risk_engine,
        telemetry_store=telemetry,
        initial_prices={"USDTTMN": 70000.0, "BTCTMN": 4500000000.0},
    )
    return harness


@pytest.fixture
def client(test_harness: SystemTradingHarness) -> TestClient:
    app = create_dashboard_app(harness=test_harness, auth_token="super-secret-token")
    return TestClient(app)


def test_dashboard_unauthenticated_requests_rejected(client: TestClient):
    # Missing auth
    res_status = client.get("/api/status")
    assert res_status.status_code == 401

    res_pause = client.post("/api/control/pause")
    assert res_pause.status_code == 401

    res_resume = client.post("/api/control/resume")
    assert res_resume.status_code == 401

    res_flatten = client.post("/api/control/flatten")
    assert res_flatten.status_code == 401

    # Invalid token
    res_bad_token = client.get("/api/status", headers={"Authorization": "Bearer wrong-token"})
    assert res_bad_token.status_code == 401


def test_dashboard_authenticated_status_endpoint(client: TestClient):
    headers = {"Authorization": "Bearer super-secret-token"}
    res = client.get("/api/status", headers=headers)
    assert res.status_code == 200

    data = res.json()
    assert data["mode"] == "shadow"
    assert data["state"] == "RUNNING"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0

    financials = data["financials"]
    assert financials["starting_balance_tmn"] == 5000000.0
    assert financials["cash_tmn"] == 5000000.0
    assert financials["equity_tmn"] == 5000000.0
    assert financials["realized_net_pnl_tmn"] == 0.0

    assert "portfolio" in data
    assert "open_positions" in data["portfolio"]
    assert "recent_telemetry" in data


def test_dashboard_control_pause_and_resume(client: TestClient, test_harness: SystemTradingHarness):
    headers = {"Authorization": "Bearer super-secret-token"}

    # Pause
    res_pause = client.post("/api/control/pause", headers=headers)
    assert res_pause.status_code == 200
    assert res_pause.json()["state"] == "PAUSED"
    assert test_harness.state == "PAUSED"

    # Status reflects paused
    res_status = client.get("/api/status", headers=headers)
    assert res_status.json()["state"] == "PAUSED"

    # In PAUSED mode, run_cycle should not scan new candidates or submit buy orders
    market_snapshot = {
        "BTCTMN": {
            "current_price": 4500000000.0,
            "bid_price": 4499000000.0,
            "ask_price": 4501000000.0,
            "volume_24h": 10000000.0,
            "spread_bps": 4.0,
            "momentum_pct": 0.05,
            "rsi_14": 55.0,
            "atr_pct": 0.02,
            "depth_imbalance": 0.1,
            "rel_vol": 1.5,
        }
    }
    result = test_harness.run_cycle(market_snapshot, timestamp=time.time())
    assert result["orders_submitted"] == 0
    assert len(test_harness.portfolio["open_positions"]) == 0

    # Resume
    res_resume = client.post("/api/control/resume", headers=headers)
    assert res_resume.status_code == 200
    assert res_resume.json()["state"] == "RUNNING"
    assert test_harness.state == "RUNNING"


def test_dashboard_control_flatten(client: TestClient, test_harness: SystemTradingHarness):
    headers = {"Authorization": "Bearer super-secret-token"}

    # Simulate an open position
    test_harness.portfolio["open_positions"]["USDTTMN"] = {
        "position_id": "pos-usdt",
        "symbol": "USDTTMN",
        "quantity": 10.0,
        "entry_price": 70000.0,
        "current_price": 70000.0,
        "unrealized_pnl_tmn": 0.0,
        "realized_pnl_tmn": 0.0,
        "cumulative_fee_tmn": 140.0,
        "stop_price": 69300.0,
        "take_profit_price": 71400.0,
        "opened_at": time.time(),
        "max_holding_seconds": 3600.0,
        "is_open": True,
    }

    res_flatten = client.post("/api/control/flatten", headers=headers)
    assert res_flatten.status_code == 200
    assert res_flatten.json()["state"] == "SAFE-STOP"
    assert res_flatten.json()["flattened_count"] == 1
    assert len(test_harness.portfolio["open_positions"]) == 0
    assert test_harness.state == "SAFE-STOP"


def test_dashboard_html_view(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Wallex Opportunity Agent" in res.text


def test_dashboard_backtest_endpoint(client: TestClient):
    headers = {"Authorization": "Bearer super-secret-token"}
    res = client.post("/api/backtest/run", json={"cycles": 10}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert data["initial_capital_tmn"] == 5000000.0
    assert "final_equity_tmn" in data
    assert "trades" in data


def test_dashboard_audit_reports_endpoint(client: TestClient):
    headers = {"Authorization": "Bearer super-secret-token"}
    res = client.get("/api/reports/audit", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "trades" in data


def test_dashboard_preflight_endpoint(client: TestClient):
    headers = {"Authorization": "Bearer super-secret-token"}
    res = client.get("/api/preflight/run", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "checks" in data
    assert "all_passed" in data


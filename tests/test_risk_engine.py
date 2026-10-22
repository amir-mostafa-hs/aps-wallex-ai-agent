import pytest
from wallex_agent.domain.types import TradeIntent, PositionRecord
from wallex_agent.risk_engine import RiskEngine, PortfolioState


def test_risk_engine_approves_valid_buy_with_correct_sizing():
    engine = RiskEngine(
        risk_per_trade_equity_pct=0.005,  # 0.5% risk
        max_position_notional_equity_pct=0.15,  # 15% max notional (750k)
        max_total_exposure_equity_pct=0.40,  # 40% max exposure (2M)
        min_cash_reserve_equity_pct=0.50,  # 50% min cash (2.5M)
        max_open_positions=3,
        min_notional_tmn=100000.0,
    )

    portfolio: PortfolioState = {
        "total_equity_tmn": 5000000.0,
        "available_cash_tmn": 5000000.0,
        "open_positions": {},
        "open_orders": {},
    }

    intent: TradeIntent = {
        "contract_version": "1.0",
        "decision_id": "dec-001",
        "cycle_id": "cyc-01",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Drop below low",
        "stop_distance_pct": 1.0,  # 1.0% stop
        "take_profit_distance_pct": 2.5,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-1"],
    }

    current_price = 4000000000.0  # 4 Billion TMN per BTC
    decision = engine.evaluate(intent, portfolio, current_price=current_price, spread_bps=10.0)

    assert decision["approved"] is True
    # Risk amount = 5,000,000 * 0.005 = 25,000 TMN
    # Sized by stop = 25,000 / 0.01 = 2,500,000 TMN
    # Max notional = 5,000,000 * 0.15 = 750,000 TMN
    # Bounded notional = min(2.5M, 750k) = 750,000 TMN
    assert decision["approved_notional"] == 750000.0
    assert decision["approved_quantity"] == pytest.approx(750000.0 / current_price)
    assert decision["reject_code"] is None


def test_risk_engine_rejects_when_cash_reserve_breached():
    engine = RiskEngine(
        min_cash_reserve_equity_pct=0.50,  # 50% must remain in cash
    )
    # Total equity 5M. Position 1M (20% exposure). Max exposure is 40% (2M).
    # Buying 750k gives total exposure 1.75M (35% < 40%, so exposure passes).
    # But cash is 2.8M. 2.8M - 750k = 2.05M (41% < 50% min cash reserve).
    portfolio: PortfolioState = {
        "total_equity_tmn": 5000000.0,
        "available_cash_tmn": 2800000.0,
        "open_positions": {
            "ETH": {"position_id": "p1", "symbol": "ETHTMN", "quantity": 1.0, "entry_price": 1000000.0, "current_price": 1000000.0, "unrealized_pnl_tmn": 0, "realized_pnl_tmn": 0, "cumulative_fee_tmn": 0, "stop_price": 950000.0, "take_profit_price": None, "opened_at": 0, "max_holding_seconds": 300, "is_open": True}
        },
        "open_orders": {},
    }

    intent: TradeIntent = {
        "contract_version": "1.0",
        "decision_id": "dec-002",
        "cycle_id": "cyc-01",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Valid breakout",
        "invalidation_condition": "Drop below low",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.5,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-1"],
    }

    decision = engine.evaluate(intent, portfolio, current_price=1000000.0)
    assert decision["approved"] is False
    assert decision["reject_code"] == "INSUFFICIENT_CASH"


def test_risk_engine_rejects_when_liquidation_floor_approached():
    engine = RiskEngine(
        liquidation_floor_tmn=900.0,
        warning_limit_tmn=1000.0,
    )
    # Catastrophic account loss: equity fell to 950 TMN (below 1000 warning floor)
    portfolio: PortfolioState = {
        "total_equity_tmn": 950.0,
        "available_cash_tmn": 950.0,
        "open_positions": {},
        "open_orders": {},
    }

    intent: TradeIntent = {
        "contract_version": "1.0",
        "decision_id": "dec-003",
        "cycle_id": "cyc-01",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Buy",
        "invalidation_condition": "Drop",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-1"],
    }

    decision = engine.evaluate(intent, portfolio, current_price=100.0)
    assert decision["approved"] is False
    assert decision["reject_code"] == "LIQUIDATION_RISK"


def test_risk_engine_rejects_max_positions_reached():
    engine = RiskEngine(max_open_positions=2)
    portfolio: PortfolioState = {
        "total_equity_tmn": 5000000.0,
        "available_cash_tmn": 4000000.0,
        "open_positions": {
            "P1": {"position_id": "p1", "symbol": "ETHTMN", "quantity": 1.0, "entry_price": 500000.0, "current_price": 500000.0, "unrealized_pnl_tmn": 0, "realized_pnl_tmn": 0, "cumulative_fee_tmn": 0, "stop_price": 490000.0, "take_profit_price": None, "opened_at": 0, "max_holding_seconds": 300, "is_open": True},
            "P2": {"position_id": "p2", "symbol": "SOLTMN", "quantity": 1.0, "entry_price": 500000.0, "current_price": 500000.0, "unrealized_pnl_tmn": 0, "realized_pnl_tmn": 0, "cumulative_fee_tmn": 0, "stop_price": 490000.0, "take_profit_price": None, "opened_at": 0, "max_holding_seconds": 300, "is_open": True},
        },
        "open_orders": {},
    }

    intent: TradeIntent = {
        "contract_version": "1.0",
        "decision_id": "dec-004",
        "cycle_id": "cyc-01",
        "symbol": "BTCTMN",
        "action": "BUY",
        "strategy_id": "momentum",
        "horizon_profile": "FAST",
        "confidence": 0.8,
        "reason_code": "SIGNAL_VALID",
        "decision_rationale": "Buy",
        "invalidation_condition": "Drop",
        "stop_distance_pct": 1.0,
        "take_profit_distance_pct": 2.0,
        "max_holding_minutes": 5,
        "parameter_overrides": {},
        "evidence_ids": ["ev-1"],
    }

    decision = engine.evaluate(intent, portfolio, current_price=100.0)
    assert decision["approved"] is False
    assert decision["reject_code"] == "POSITION_LIMIT"

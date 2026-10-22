import os
import pytest
from wallex_agent.config import load_config, AppConfig


def test_default_config_is_shadow_mode_and_fail_closed():
    # Empty environment should safely default to shadow mode with live disabled
    config = load_config({})
    assert config["mode"] == "shadow"
    assert config["live_trading_enabled"] is False
    assert config["live_preflight_acknowledged"] is False
    assert config["risk_per_trade_equity_pct"] == 0.005
    assert config["max_position_notional_equity_pct"] == 0.15
    assert config["max_total_exposure_equity_pct"] == 0.40
    assert config["min_cash_reserve_equity_pct"] == 0.50
    assert config["max_open_positions"] == 3
    assert config["liquidation_floor_tmn"] == 900.0
    assert config["warning_limit_tmn"] == 1000.0
    assert config["pre_expiry_exit_hours"] == 2.0


def test_live_mode_without_explicit_flags_fails_closed():
    # Attempting MODE=live without acknowledgement must raise ValueError or fallback
    env = {
        "MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "LIVE_PREFLIGHT_ACKNOWLEDGED": "false",
    }
    with pytest.raises(ValueError, match="LIVE_PREFLIGHT_ACKNOWLEDGED"):
        load_config(env)


def test_live_mode_with_all_flags_accepted():
    env = {
        "MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "LIVE_PREFLIGHT_ACKNOWLEDGED": "true",
        "WALLEX_API_KEY": "test-key",
        "SUB_ACCOUNT_CLIENT_ID": "sub-123",
    }
    config = load_config(env)
    assert config["mode"] == "live"
    assert config["live_trading_enabled"] is True
    assert config["live_preflight_acknowledged"] is True
    assert config["wallex_api_key"] == "test-key"
    assert config["sub_account_client_id"] == "sub-123"


def test_invalid_risk_pct_raises_error():
    env = {
        "RISK_PER_TRADE_EQUITY_PCT": "1.5",  # Over 100%
    }
    with pytest.raises(ValueError, match="RISK_PER_TRADE_EQUITY_PCT"):
        load_config(env)

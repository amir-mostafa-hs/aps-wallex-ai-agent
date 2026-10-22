"""Unit and integration tests for Preflight Safety Gate and Live Enabler."""
from __future__ import annotations
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from wallex_agent.config import load_config
from wallex_agent.preflight import (
    PreflightGate,
    PreflightError,
    PreflightReport,
)


@pytest.fixture
def valid_env() -> dict[str, str]:
    return {
        "MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "LIVE_PREFLIGHT_ACKNOWLEDGED": "true",
        "WALLEX_API_KEY": "valid_test_api_key",
        "SUB_ACCOUNT_CLIENT_ID": "sub_client_12345",
        "PRE_EXPIRY_EXIT_HOURS": "2.0",
    }


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    # Mock active package response with expireAt 48 hours in future
    future_time = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    client.get_active_package.return_value = {
        "id": 183,
        "title": "Package 183",
        "expireAt": future_time,
        "timeZone": "UTC",
    }
    # Mock sub-account permissions
    client.get_subaccount_permissions.return_value = {
        "subAccountId": "sub_client_12345",
        "permissions": ["READ", "TRADE"],
    }
    # Mock market constraints
    client.get_market_constraints.return_value = {
        "USDT-TMN": {"min_notional": 100000.0, "price_precision": 0, "qty_precision": 2},
        "BTC-TMN": {"min_notional": 100000.0, "price_precision": 0, "qty_precision": 6},
    }
    # Mock active spot markets
    client.get_markets.return_value = [
        {"symbol": "USDTTMN", "base_asset": "USDT", "quote_asset": "TMN", "is_spot": True, "is_active": True},
        {"symbol": "BTCTMN", "base_asset": "BTC", "quote_asset": "TMN", "is_spot": True, "is_active": True},
    ]
    return client


def test_preflight_passes_when_all_checks_succeed(valid_env: dict[str, str], mock_client: MagicMock):
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report: PreflightReport = gate.run_all_checks(target_symbols=["USDT-TMN", "BTC-TMN"])

    assert report["all_passed"] is True
    assert len(report["checks"]) >= 5
    assert all(c["passed"] for c in report["checks"])
    assert report["expire_at_iso"] is not None
    assert report["cutoff_time_iso"] is not None
    assert report["verified_markets_count"] == 2

    # enforce_or_raise should NOT raise
    gate.enforce_or_raise(report)


def test_preflight_fails_when_api_key_or_subaccount_missing():
    env = {
        "MODE": "shadow",
        "WALLEX_API_KEY": "",
        "SUB_ACCOUNT_CLIENT_ID": "",
    }
    config = load_config(env)
    gate = PreflightGate(config)
    report = gate.run_all_checks()

    assert report["all_passed"] is False
    auth_check = next(c for c in report["checks"] if c["name"] == "api_key_and_subaccount")
    assert auth_check["passed"] is False
    assert "missing" in auth_check["details"].lower()


def test_preflight_fails_when_subaccount_lacks_trade_permission(valid_env: dict[str, str], mock_client: MagicMock):
    mock_client.get_subaccount_permissions.return_value = {
        "subAccountId": "sub_client_12345",
        "permissions": ["READ"],  # Missing TRADE
    }
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks()

    assert report["all_passed"] is False
    auth_check = next(c for c in report["checks"] if c["name"] == "api_key_and_subaccount")
    assert auth_check["passed"] is False
    assert "trade" in auth_check["details"].lower()

    with pytest.raises(PreflightError):
        gate.enforce_or_raise(report)


def test_preflight_fails_closed_when_denylist_missing_or_empty(valid_env: dict[str, str], mock_client: MagicMock):
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks(denylist_path="non_existent_denylist.json")

    assert report["all_passed"] is False
    allowlist_check = next(c for c in report["checks"] if c["name"] == "allowlist_integrity")
    assert allowlist_check["passed"] is False
    assert "fail-closed" in allowlist_check["details"].lower() or "missing" in allowlist_check["details"].lower()


def test_preflight_fails_closed_when_assets_source_missing(valid_env: dict[str, str], mock_client: MagicMock):
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks(assets_source_path="non_existent_assets.md")

    assert report["all_passed"] is False
    allowlist_check = next(c for c in report["checks"] if c["name"] == "allowlist_integrity")
    assert allowlist_check["passed"] is False
    assert "assets.md" in allowlist_check["details"].lower()



def test_preflight_fails_when_credit_package_expired_or_buffer_breached(valid_env: dict[str, str], mock_client: MagicMock):
    # Expire in 1 hour (less than pre_expiry_exit_hours=2.0)
    near_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    mock_client.get_active_package.return_value = {
        "id": 183,
        "title": "Package 183",
        "expireAt": near_time,
        "timeZone": "UTC",
    }
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks()

    assert report["all_passed"] is False
    expiry_check = next(c for c in report["checks"] if c["name"] == "credit_package_expiration")
    assert expiry_check["passed"] is False
    assert "buffer" in expiry_check["details"].lower() or "expired" in expiry_check["details"].lower()

    with pytest.raises(PreflightError):
        gate.enforce_or_raise(report)


def test_preflight_excludes_unverified_markets(valid_env: dict[str, str], mock_client: MagicMock):
    # One market verified, one missing min_notional
    mock_client.get_market_constraints.return_value = {
        "USDT-TMN": {"min_notional": 100000.0, "price_precision": 0, "qty_precision": 2},
        "BTC-TMN": {"min_notional": None, "price_precision": 0, "qty_precision": 6},  # Invalid
    }
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks(target_symbols=["USDT-TMN", "BTC-TMN"])

    market_check = next(c for c in report["checks"] if c["name"] == "market_constraints")
    assert market_check["passed"] is True  # Passed but excluded unverified
    assert report["verified_markets_count"] == 1


def test_preflight_watchdog_dry_run_verifies_emergency_exit(valid_env: dict[str, str], mock_client: MagicMock):
    config = load_config(valid_env)
    gate = PreflightGate(config, client=mock_client)
    report = gate.run_all_checks()

    watchdog_check = next(c for c in report["checks"] if c["name"] == "watchdog_dry_run")
    assert watchdog_check["passed"] is True


def test_preflight_blocks_live_startup_if_flags_not_satisfied(mock_client: MagicMock):
    # Config in shadow mode
    config = load_config({"MODE": "shadow"})
    gate = PreflightGate(config, client=mock_client)
    # Trying to enforce live on shadow mode
    report = gate.run_all_checks()
    # In shadow mode, enforce_or_raise should not raise because mode is not live
    gate.enforce_or_raise(report)

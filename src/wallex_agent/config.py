"""Configuration loader and validator for Wallex Opportunity Agent."""
from __future__ import annotations
import os
from typing import TypedDict, Literal, Mapping, Any


class AppConfig(TypedDict):
    mode: Literal["backtest", "shadow", "live"]
    live_trading_enabled: bool
    live_preflight_acknowledged: bool
    wallex_api_key: str
    sub_account_client_id: str
    wallex_base_url: str
    risk_per_trade_equity_pct: float
    max_position_notional_equity_pct: float
    max_total_exposure_equity_pct: float
    min_cash_reserve_equity_pct: float
    max_open_positions: int
    default_min_notional_tmn: float
    default_min_notional_usdt: float
    scan_interval_seconds: float
    max_execution_quote_age_seconds: float
    max_candidate_snapshot_age_seconds: float
    pre_expiry_exit_hours: float
    liquidation_floor_tmn: float
    warning_limit_tmn: float
    sqlite_db_path: str


def _to_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes", "on")


def load_config(env: Mapping[str, str] | None = None) -> AppConfig:
    """Load configuration from environment mapping or os.environ.
    
    Applies strict fail-closed validation for live mode and numerical bounds.
    """
    source = os.environ if env is None else env

    raw_mode = source.get("MODE", "shadow").strip().lower()
    if raw_mode not in ("backtest", "shadow", "live"):
        raise ValueError(f"Invalid MODE '{raw_mode}'. Must be 'backtest', 'shadow', or 'live'.")
    mode: Literal["backtest", "shadow", "live"] = raw_mode  # type: ignore

    live_trading_enabled = _to_bool(source.get("LIVE_TRADING_ENABLED", False))
    live_preflight_acknowledged = _to_bool(source.get("LIVE_PREFLIGHT_ACKNOWLEDGED", False))

    # Gating check: live mode requires explicit enablement and preflight acknowledgement
    if mode == "live":
        if not live_trading_enabled:
            raise ValueError("MODE is set to 'live' but LIVE_TRADING_ENABLED is not true.")
        if not live_preflight_acknowledged:
            raise ValueError("MODE is set to 'live' but LIVE_PREFLIGHT_ACKNOWLEDGED is not true.")

    risk_per_trade = float(source.get("RISK_PER_TRADE_EQUITY_PCT", "0.005"))
    if not (0.0 < risk_per_trade <= 0.10):
        raise ValueError(
            f"RISK_PER_TRADE_EQUITY_PCT must be between 0.0 and 0.10 (got {risk_per_trade})."
        )

    max_position_notional = float(source.get("MAX_POSITION_NOTIONAL_EQUITY_PCT", "0.15"))
    if not (0.0 < max_position_notional <= 0.50):
        raise ValueError(f"MAX_POSITION_NOTIONAL_EQUITY_PCT out of range: {max_position_notional}")

    max_total_exposure = float(source.get("MAX_TOTAL_EXPOSURE_EQUITY_PCT", "0.40"))
    if not (0.0 < max_total_exposure <= 1.0):
        raise ValueError(f"MAX_TOTAL_EXPOSURE_EQUITY_PCT out of range: {max_total_exposure}")

    min_cash_reserve = float(source.get("MIN_CASH_RESERVE_EQUITY_PCT", "0.50"))
    if not (0.0 <= min_cash_reserve < 1.0):
        raise ValueError(f"MIN_CASH_RESERVE_EQUITY_PCT out of range: {min_cash_reserve}")

    return {
        "mode": mode,
        "live_trading_enabled": live_trading_enabled,
        "live_preflight_acknowledged": live_preflight_acknowledged,
        "wallex_api_key": source.get("WALLEX_API_KEY", "").strip(),
        "sub_account_client_id": source.get("SUB_ACCOUNT_CLIENT_ID", "").strip(),
        "wallex_base_url": source.get("WALLEX_BASE_URL", "https://api.wallex.ir").rstrip("/"),
        "risk_per_trade_equity_pct": risk_per_trade,
        "max_position_notional_equity_pct": max_position_notional,
        "max_total_exposure_equity_pct": max_total_exposure,
        "min_cash_reserve_equity_pct": min_cash_reserve,
        "max_open_positions": int(source.get("MAX_OPEN_POSITIONS", "3")),
        "default_min_notional_tmn": float(source.get("DEFAULT_MIN_NOTIONAL_TMN", "100000.0")),
        "default_min_notional_usdt": float(source.get("DEFAULT_MIN_NOTIONAL_USDT", "10.0")),
        "scan_interval_seconds": float(source.get("SCAN_INTERVAL_SECONDS", "15.0")),
        "max_execution_quote_age_seconds": float(source.get("MAX_EXECUTION_QUOTE_AGE_SECONDS", "5.0")),
        "max_candidate_snapshot_age_seconds": float(source.get("MAX_CANDIDATE_SNAPSHOT_AGE_SECONDS", "45.0")),
        "pre_expiry_exit_hours": float(source.get("PRE_EXPIRY_EXIT_HOURS", "2.0")),
        "liquidation_floor_tmn": float(source.get("LIQUIDATION_FLOOR_TMN", "900.0")),
        "warning_limit_tmn": float(source.get("WARNING_LIMIT_TMN", "1000.0")),
        "sqlite_db_path": source.get("SQLITE_DB_PATH", "wallex_agent.db").strip(),
    }


DEFAULT_STRATEGY_SETTINGS: dict[str, Any] = {
    "default_strategy_id": "trend_filtered_pullback",
    "default_stop_distance_pct": 1.0,
    "default_take_profit_distance_pct": 2.0,
    "default_max_holding_minutes": 10,
    "default_cycles": 50,
}


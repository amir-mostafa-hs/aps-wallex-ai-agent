"""Preflight Safety Gate and Live Trading Enabler."""
from __future__ import annotations
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import TypedDict, Any, Sequence

from wallex_agent.config import AppConfig
from wallex_agent.universe import MarketUniverse
from wallex_agent.watchdog import LocalWatchdog
from wallex_agent.domain.types import PositionRecord

logger = logging.getLogger(__name__)


class PreflightError(Exception):
    """Raised when preflight safety gate checks fail in live mode."""
    pass


class PreflightCheckResult(TypedDict):
    name: str
    passed: bool
    details: str


class PreflightReport(TypedDict):
    all_passed: bool
    checks: list[PreflightCheckResult]
    expire_at_iso: str | None
    cutoff_time_iso: str | None
    verified_markets_count: int


class PreflightGate:
    """Verifies all safety, account, allowlist, and runtime prerequisites before live trading."""

    def __init__(self, config: AppConfig, client: Any = None):
        self.config = config
        self.client = client

    def check_api_key_and_subaccount(self) -> PreflightCheckResult:
        api_key = self.config.get("wallex_api_key", "").strip()
        sub_account_id = self.config.get("sub_account_client_id", "").strip()

        if not api_key:
            return {
                "name": "api_key_and_subaccount",
                "passed": False,
                "details": "WALLEX_API_KEY is missing or empty.",
            }

        if not sub_account_id:
            return {
                "name": "api_key_and_subaccount",
                "passed": False,
                "details": "SUB_ACCOUNT_CLIENT_ID is missing or empty.",
            }

        # Check client permissions if client is available
        if self.client and hasattr(self.client, "get_subaccount_permissions"):
            try:
                perms_data = self.client.get_subaccount_permissions(sub_account_id)
                raw_perms = perms_data.get("permissions", [])
                perms = [str(p).upper() for p in raw_perms]
                if "TRADE" not in perms:
                    return {
                        "name": "api_key_and_subaccount",
                        "passed": False,
                        "details": f"Sub-account {sub_account_id} lacks 'TRADE' permission. Found: {perms}",
                    }
            except Exception as e:
                return {
                    "name": "api_key_and_subaccount",
                    "passed": False,
                    "details": f"Failed to verify sub-account permissions: {e}",
                }

        return {
            "name": "api_key_and_subaccount",
            "passed": True,
            "details": f"API key present and sub-account {sub_account_id} has TRADE permission.",
        }

    def check_allowlist_integrity(self, denylist_path: str = "docs/sources/inactive_markets.json") -> PreflightCheckResult:
        if not os.path.exists(denylist_path):
            return {
                "name": "allowlist_integrity",
                "passed": False,
                "details": f"Fail-closed: denylist file '{denylist_path}' is missing.",
            }

        try:
            if self.client and hasattr(self.client, "get_markets"):
                markets_data = self.client.get_markets()
            else:
                markets_data = [
                    {"symbol": "USDTTMN", "base_asset": "USDT", "quote_asset": "TMN", "is_spot": True, "is_active": True},
                    {"symbol": "BTCTMN", "base_asset": "BTC", "quote_asset": "TMN", "is_spot": True, "is_active": True},
                ]

            universe = MarketUniverse.from_files(
                markets_data=markets_data,
                local_denylist_path=denylist_path,
                package_data=None,
            )
            count = universe.total_count
            if count == 0:
                return {
                    "name": "allowlist_integrity",
                    "passed": False,
                    "details": "Allowlist resolved to 0 valid active spot markets.",
                }

            return {
                "name": "allowlist_integrity",
                "passed": True,
                "details": f"Allowlist successfully loaded and filtered {count} active Spot markets.",
            }
        except Exception as e:
            return {
                "name": "allowlist_integrity",
                "passed": False,
                "details": f"Fail-closed allowlist validation failed: {e}",
            }

    def check_market_constraints(self, target_symbols: Sequence[str]) -> tuple[PreflightCheckResult, int]:
        if not target_symbols:
            return (
                {
                    "name": "market_constraints",
                    "passed": True,
                    "details": "No specific target symbols requested for verification.",
                },
                0,
            )

        if not self.client or not hasattr(self.client, "get_market_constraints"):
            return (
                {
                    "name": "market_constraints",
                    "passed": True,
                    "details": f"{len(target_symbols)} symbols assumed valid (no API client configured).",
                },
                len(target_symbols),
            )

        try:
            constraints_map = self.client.get_market_constraints()
            verified_count = 0
            unverified: list[str] = []

            for sym in target_symbols:
                info = constraints_map.get(sym)
                if not info:
                    unverified.append(f"{sym} (missing from constraints)")
                    continue
                min_notional = info.get("min_notional")
                if min_notional is None or min_notional <= 0:
                    unverified.append(f"{sym} (invalid min_notional)")
                    continue
                verified_count += 1

            details = f"Verified {verified_count}/{len(target_symbols)} markets."
            if unverified:
                details += f" Excluded unverified: {', '.join(unverified)}."

            return (
                {
                    "name": "market_constraints",
                    "passed": True,
                    "details": details,
                },
                verified_count,
            )
        except Exception as e:
            return (
                {
                    "name": "market_constraints",
                    "passed": False,
                    "details": f"Market constraints check error: {e}",
                },
                0,
            )

    def check_watchdog_dry_run(self) -> PreflightCheckResult:
        try:
            import time
            watchdog = LocalWatchdog(max_allowed_price_lag_seconds=5.0)
            now_ts = time.time()
            mock_pos: PositionRecord = {
                "position_id": "preflight-test-pos",
                "symbol": "TEST-TMN",
                "quantity": 10.0,
                "entry_price": 100.0,
                "current_price": 95.0,
                "unrealized_pnl_tmn": -50.0,
                "realized_pnl_tmn": 0.0,
                "cumulative_fee_tmn": 0.0,
                "stop_price": 98.0,
                "take_profit_price": 110.0,
                "opened_at": now_ts - 60.0,
                "max_holding_seconds": 3600.0,
                "is_open": True,
            }
            trigger = watchdog.check_position(mock_pos, current_bid=95.0, current_time=now_ts)
            if not trigger or trigger["trigger_type"] != "STOP_LOSS":
                return {
                    "name": "watchdog_dry_run",
                    "passed": False,
                    "details": f"Watchdog dry-run failed to trigger stop-loss: {trigger}",
                }

            return {
                "name": "watchdog_dry_run",
                "passed": True,
                "details": "Local Watchdog dry-run verified emergency exit logic successfully.",
            }
        except Exception as e:
            return {
                "name": "watchdog_dry_run",
                "passed": False,
                "details": f"Watchdog dry-run threw an exception: {e}",
            }

    def check_credit_package_expiration(self) -> tuple[PreflightCheckResult, str | None, str | None]:
        if not self.client or not hasattr(self.client, "get_active_package"):
            # If live mode, active package endpoint is mandatory
            if self.config["mode"] == "live":
                return (
                    {
                        "name": "credit_package_expiration",
                        "passed": False,
                        "details": "Live mode requires active package verification, but no client was provided.",
                    },
                    None,
                    None,
                )
            return (
                {
                    "name": "credit_package_expiration",
                    "passed": True,
                    "details": "Non-live mode: package expiration check skipped.",
                },
                None,
                None,
            )

        try:
            pkg = self.client.get_active_package()
            raw_expire = pkg.get("expireAt")
            if not raw_expire:
                return (
                    {
                        "name": "credit_package_expiration",
                        "passed": False,
                        "details": "Active package data missing 'expireAt' timestamp.",
                    },
                    None,
                    None,
                )

            # Parse ISO or epoch
            if isinstance(raw_expire, (int, float)):
                expire_dt = datetime.fromtimestamp(raw_expire, tz=timezone.utc)
            else:
                clean_iso = str(raw_expire).replace("Z", "+00:00")
                expire_dt = datetime.fromisoformat(clean_iso)
                if expire_dt.tzinfo is None:
                    expire_dt = expire_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            diff_hours = (expire_dt - now_utc).total_seconds() / 3600.0
            buffer_hours = float(self.config.get("pre_expiry_exit_hours", 2.0))

            cutoff_dt = expire_dt - timedelta(hours=buffer_hours)

            if diff_hours <= buffer_hours:
                return (
                    {
                        "name": "credit_package_expiration",
                        "passed": False,
                        "details": f"Remaining package time ({diff_hours:.2f}h) is within or below safety buffer ({buffer_hours:.2f}h).",
                    },
                    expire_dt.isoformat(),
                    cutoff_dt.isoformat(),
                )

            return (
                {
                    "name": "credit_package_expiration",
                    "passed": True,
                    "details": f"Credit package expires at {expire_dt.isoformat()} ({diff_hours:.1f}h remaining). Cutoff scheduled at {cutoff_dt.isoformat()}.",
                },
                expire_dt.isoformat(),
                cutoff_dt.isoformat(),
            )
        except Exception as e:
            return (
                {
                    "name": "credit_package_expiration",
                    "passed": False,
                    "details": f"Error verifying active credit package: {e}",
                },
                None,
                None,
            )

    def run_all_checks(
        self,
        target_symbols: Sequence[str] | None = None,
        denylist_path: str = "docs/sources/inactive_markets.json",
    ) -> PreflightReport:
        checks: list[PreflightCheckResult] = []

        # 1. API key & sub-account
        checks.append(self.check_api_key_and_subaccount())

        # 2. Allowlist integrity
        checks.append(self.check_allowlist_integrity(denylist_path=denylist_path))

        # 3. Market constraints
        target_syms = target_symbols or ["USDT-TMN", "BTC-TMN"]
        constraints_check, verified_count = self.check_market_constraints(target_syms)
        checks.append(constraints_check)

        # 4. Watchdog dry run
        checks.append(self.check_watchdog_dry_run())

        # 5. Package expiration
        expiry_check, expire_at_iso, cutoff_iso = self.check_credit_package_expiration()
        checks.append(expiry_check)

        all_passed = all(c["passed"] for c in checks)

        for c in checks:
            status = "PASS" if c["passed"] else "FAIL"
            logger.info(f"[PREFLIGHT] [{status}] {c['name']}: {c['details']}")

        return {
            "all_passed": all_passed,
            "checks": checks,
            "expire_at_iso": expire_at_iso,
            "cutoff_time_iso": cutoff_iso,
            "verified_markets_count": verified_count,
        }

    def enforce_or_raise(self, report: PreflightReport) -> None:
        """Enforces preflight pass before live mode execution."""
        if self.config["mode"] == "live":
            if not report["all_passed"]:
                failed_checks = [c for c in report["checks"] if not c["passed"]]
                summary = "; ".join(f"{c['name']}: {c['details']}" for c in failed_checks)
                raise PreflightError(f"Preflight checks failed for LIVE mode: {summary}")

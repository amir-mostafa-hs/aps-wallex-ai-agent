"""Command-line interface and runners for Wallex Opportunity Agent."""
from __future__ import annotations
import argparse
import sys
import time
import os
import threading
from typing import Sequence
import dotenv

from wallex_agent.config import load_config, AppConfig
from wallex_agent.universe import MarketUniverse
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine
from wallex_agent.telemetry import TelemetryStore
from wallex_agent.harness import SystemTradingHarness
from wallex_agent.preflight import PreflightGate, PreflightReport
from wallex_agent.dashboard import create_dashboard_app


def run_preflight_cmd(args: argparse.Namespace) -> int:
    """Executes preflight verification checks and outputs status table."""
    dotenv.load_dotenv()
    print("=" * 60)
    print(" WALLEX OPPORTUNITY AGENT - PREFLIGHT VERIFICATION GATE")
    print("=" * 60)

    try:
        config = load_config()
    except Exception as exc:
        print(f"[FAIL] Configuration error: {exc}")
        return 1

    gate = PreflightGate(config)
    report = gate.run_all_checks()

    print(f"\nTarget Mode: {config['mode'].upper()}")
    print("-" * 60)
    for check in report["checks"]:
        status_sym = "[PASS]" if check["passed"] else "[FAIL]"
        print(f"{status_sym:<7} {check['name']:<25} | {check['details']}")
    print("-" * 60)

    if report["expire_at_iso"]:
        print(f"Credit Package Expiry: {report['expire_at_iso']}")
        print(f"Trade Cutoff Scheduled: {report['cutoff_time_iso']}")

    if report["all_passed"]:
        print("\n>>> ALL PREFLIGHT SAFETY GATES PASSED <<<")
        if config["mode"] == "live":
            print("System is verified and authorized for LIVE execution.")
        else:
            print(f"System is verified for {config['mode'].upper()} execution.")
        return 0
    else:
        print("\n>>> PREFLIGHT CHECKS FAILED - LIVE TRADING LOCKED <<<")
        return 1


def run_backtest_cmd(args: argparse.Namespace) -> int:
    """Executes multi-scenario historical backtest and prints performance report."""
    dotenv.load_dotenv()
    cycles_to_run = getattr(args, "cycles", 50)
    print("=" * 60)
    print(f" RUNNING BACKTEST SIMULATION ({cycles_to_run} CYCLES)")
    print("=" * 60)

    telemetry = TelemetryStore(db_path=":memory:")
    telemetry.initialize()

    raw_markets = [
        {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 6, "price_precision": 0},
        {"symbol": "ETHTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0},
        {"symbol": "USDTTMN", "is_spot": True, "is_active": True, "amount_precision": 2, "price_precision": 0},
    ]
    universe = MarketUniverse.build(
        markets=raw_markets,
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )

    harness = SystemTradingHarness(
        mode="backtest",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(),
        risk_engine=RiskEngine(
            risk_per_trade_equity_pct=0.005,
            max_position_notional_equity_pct=0.15,
            min_notional_tmn=100000.0,
        ),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4500000000.0, "ETHTMN": 250000000.0, "USDTTMN": 70000.0},
    )

    base_prices = {"BTCTMN": 4500000000.0, "ETHTMN": 250000000.0, "USDTTMN": 70000.0}

    # Simulate price action over cycles
    for cycle in range(cycles_to_run):
        t = 1000.0 + (cycle * 15.0)
        # Add slight oscillation
        drift = 1.0 + (0.002 * (1 if cycle % 3 == 0 else (-1 if cycle % 5 == 0 else 0.5)))
        snapshot = {}
        for sym, price in base_prices.items():
            curr_p = price * (drift ** (cycle + 1))
            snapshot[sym] = {
                "current_price": curr_p,
                "features": {
                    "return_pct": (drift - 1.0) * 100,
                    "relative_volume": 1.5 + (0.1 * (cycle % 4)),
                    "volatility": 0.015,
                    "latest_volume": 500000.0,
                },
                "spread_bps": 15.0,
                "is_stale": False,
                "evidence_ids": [f"ev-{sym}-{cycle}"],
            }
        harness.run_cycle(snapshot, timestamp=t)

    # Liquidate remaining positions before end of simulation
    harness.liquidate_all_positions(reason="END_OF_BACKTEST")

    # Metrics
    summary = telemetry.get_performance_summary()
    init_cash = 5000000.0
    final_equity = harness.portfolio["total_equity_tmn"]
    net_pnl = final_equity - init_cash
    roi_pct = (net_pnl / init_cash) * 100

    print("\n" + "=" * 60)
    print(" BACKTEST PERFORMANCE REPORT")
    print("=" * 60)
    print(f"Initial Capital:      {init_cash:>15,.0f} TMN")
    print(f"Final Equity:         {final_equity:>15,.0f} TMN")
    print(f"Net Realized P&L:     {net_pnl:>15,.0f} TMN ({roi_pct:+.2f}%)")
    print(f"Total Closed Trades:  {summary['total_trades']:>15}")
    print(f"Winning Trades:       {summary['winning_trades']:>15}")
    print(f"Losing Trades:        {summary['losing_trades']:>15}")
    print(f"Win Rate:             {summary['win_rate_pct']:>14.1f}%")
    print(f"Total Fees Paid:      {summary['total_fees_tmn']:>15,.0f} TMN")
    print(f"Max Drawdown:         {summary['max_drawdown_pct']:>14.2f}%")
    print("=" * 60)
    return 0


def run_shadow_cmd(args: argparse.Namespace) -> int:
    """Starts the agent in Shadow mode with real-time Dashboard."""
    dotenv.load_dotenv()
    print("=" * 60)
    print(" WALLEX OPPORTUNITY AGENT - SHADOW MODE RUNNER")
    print("=" * 60)

    try:
        config = load_config()
    except Exception as exc:
        print(f"[FAIL] Configuration load error: {exc}")
        return 1

    # Preflight validation check
    gate = PreflightGate(config)
    report = gate.run_all_checks()
    if not report["all_passed"]:
        print("[WARN] Some preflight checks raised warnings:")
        for c in report["checks"]:
            if not c["passed"]:
                print(f"  - {c['name']}: {c['details']}")

    # Setup telemetry and components
    telemetry = TelemetryStore(db_path=config.get("sqlite_db_path", "wallex_agent.db"))
    telemetry.initialize()

    # Load Universe
    try:
        raw_markets = [
            {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 6, "price_precision": 0},
            {"symbol": "ETHTMN", "is_spot": True, "is_active": True, "amount_precision": 4, "price_precision": 0},
            {"symbol": "USDTTMN", "is_spot": True, "is_active": True, "amount_precision": 2, "price_precision": 0},
        ]
        universe = MarketUniverse.build(
            markets=raw_markets,
            local_denylist=["DUMMY/TMN"],
            package_unavailable=[],
        )
    except Exception as e:
        print(f"[FAIL] Universe initialization failed: {e}")
        return 1

    harness = SystemTradingHarness(
        mode="shadow",
        initial_cash_tmn=5000000.0,
        universe=universe,
        decision_agent=DecisionAgent(),
        risk_engine=RiskEngine(
            risk_per_trade_equity_pct=config["risk_per_trade_equity_pct"],
            max_position_notional_equity_pct=config["max_position_notional_equity_pct"],
            min_notional_tmn=config["default_min_notional_tmn"],
            liquidation_floor_tmn=config["liquidation_floor_tmn"],
        ),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4500000000.0, "ETHTMN": 250000000.0, "USDTTMN": 70000.0},
    )

    auth_token = os.environ.get("DASHBOARD_ACCESS_TOKEN", "secret-token")
    dashboard_app = create_dashboard_app(harness=harness, auth_token=auth_token)

    port = int(os.environ.get("DASHBOARD_PORT", "8000"))
    host = os.environ.get("DASHBOARD_BIND", "127.0.0.1")

    # Start FastAPI dashboard in background thread
    import uvicorn
    server_thread = threading.Thread(
        target=uvicorn.run,
        args=(dashboard_app,),
        kwargs={"host": host, "port": port, "log_level": "warning"},
        daemon=True,
    )
    server_thread.start()

    print(f"\n[INFO] Dashboard running at: http://{host}:{port}")
    print(f"[INFO] Control Token: {auth_token}")
    print("[INFO] Press Ctrl+C to gracefully stop shadow execution.\n")

    # Trading cycle loop
    cycle_count = 0
    interval = config.get("scan_interval_seconds", 15.0)
    try:
        while True:
            cycle_count += 1
            now_ts = time.time()
            # Feed current market snapshot
            snapshot = {
                "BTCTMN": {
                    "current_price": 4500000000.0 + ((cycle_count % 5) * 5000000),
                    "features": {"return_pct": 0.4, "relative_volume": 1.4, "volatility": 0.01, "latest_volume": 2000000.0},
                    "spread_bps": 12.0,
                    "is_stale": False,
                    "evidence_ids": [f"ev-btc-{cycle_count}"],
                },
                "USDTTMN": {
                    "current_price": 70000.0,
                    "features": {"return_pct": 0.05, "relative_volume": 1.0, "volatility": 0.002, "latest_volume": 10000000.0},
                    "spread_bps": 8.0,
                    "is_stale": False,
                    "evidence_ids": [f"ev-usdt-{cycle_count}"],
                },
            }
            res = harness.run_cycle(snapshot, timestamp=now_ts)
            print(
                f"[CYCLE #{cycle_count:>3}] State: {harness.state:<9} | "
                f"Equity: {res['total_equity']:>10,.0f} TMN | "
                f"Cash: {res['available_cash']:>10,.0f} TMN | "
                f"Positions: {res['open_positions_count']}"
            )
            time.sleep(min(interval, 5.0))  # Smooth cadence
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down shadow runner...")
        harness.liquidate_all_positions(reason="OPERATOR_SHUTDOWN")
        print("[INFO] All open positions liquidated into TMN.")
        return 0


def run_report_cmd(args: argparse.Namespace) -> int:
    """Reads telemetry database and displays performance audit report."""
    dotenv.load_dotenv()
    db_path = os.environ.get("SQLITE_DB_PATH", "wallex_agent.db")
    if not os.path.exists(db_path):
        print(f"[WARN] No telemetry database found at: {db_path}")
        print("Run a backtest or shadow session first to generate data.")
        return 0

    telemetry = TelemetryStore(db_path=db_path)
    summary = telemetry.get_performance_summary()
    audit_trades = telemetry.get_recent_trades(limit=20)

    print("=" * 60)
    print(" WALLEX OPPORTUNITY AGENT - TELEMETRY AUDIT REPORT")
    print("=" * 60)
    print(f"Total Trades Logged:  {summary['total_trades']:>15}")
    print(f"Winning Trades:       {summary['winning_trades']:>15}")
    print(f"Losing Trades:        {summary['losing_trades']:>15}")
    print(f"Win Rate:             {summary['win_rate_pct']:>14.1f}%")
    print(f"Net Realized P&L:     {summary['net_realized_pnl_tmn']:>15,.0f} TMN")
    print(f"Total Fees Incurred:  {summary['total_fees_tmn']:>15,.0f} TMN")
    print("-" * 60)

    if audit_trades:
        print("\nRECENT TRADES AUDIT (LAST 20):")
        print(f"{'SYMBOL':<10} {'SIDE':<5} {'NET P&L (TMN)':<15} {'FEE (TMN)':<12} {'EXIT REASON':<20} {'LOSS CAUSE'}")
        print("-" * 75)
        for t in audit_trades:
            loss = t.get("loss_cause") or "N/A"
            print(
                f"{t['symbol']:<10} "
                f"{'SELL':<5} "
                f"{t['net_realized_pnl_tmn']:>12,.0f} TMN "
                f"{t['total_fee_tmn']:>10,.0f} TMN "
                f"{t['exit_reason']:<20} "
                f"{loss}"
            )
    else:
        print("No completed trades recorded yet.")

    print("=" * 60)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wallex-agent",
        description="Wallex Opportunity Trading Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Agent command to execute")

    # preflight
    subparsers.add_parser("preflight", help="Run preflight security and environment checks")

    # shadow
    subparsers.add_parser("shadow", help="Run in Shadow mode with real-time UI dashboard")

    # backtest
    bt_parser = subparsers.add_parser("backtest", help="Run historical backtest simulation")
    bt_parser.add_argument("--cycles", type=int, default=50, help="Number of simulation cycles")

    # report
    subparsers.add_parser("report", help="Print audit and performance report from SQLite database")

    args = parser.parse_args(argv)

    if args.command == "preflight":
        return run_preflight_cmd(args)
    elif args.command == "shadow":
        return run_shadow_cmd(args)
    elif args.command == "backtest":
        return run_backtest_cmd(args)
    elif args.command == "report":
        return run_report_cmd(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

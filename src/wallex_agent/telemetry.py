"""SQLite WAL telemetry logging, dual P&L calculation, and post-trade loss auditing."""
from __future__ import annotations
import json
import sqlite3
from typing import Any, Mapping, Sequence, Literal
from wallex_agent.domain.types import TradeRecord
from wallex_agent.domain.accounting import compute_trade_pnl, calculate_mtm_equity_decimal


def calculate_trade_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    entry_fee: float = 0.0,
    exit_fee: float = 0.0,
) -> tuple[float, float]:
    """Calculates deterministic gross and net realized P&L in TMN via Decimal accounting."""
    res = compute_trade_pnl(entry_price, exit_price, quantity, entry_fee, exit_fee)
    return (float(res["gross_pnl"]), float(res["net_pnl"]))


def calculate_mtm_equity(
    cash: float,
    positions: Mapping[str, Mapping[str, Any]],
    current_bids: Mapping[str, float],
) -> tuple[float, float]:
    """Calculates Mark-to-Market Total Equity and Unrealized P&L in TMN via Decimal accounting."""
    eq, pnl = calculate_mtm_equity_decimal(cash, positions, current_bids)
    return (float(eq), float(pnl))


def classify_loss_cause(
    exit_reason: str,
    net_pnl: float,
    market_context: Mapping[str, Any],
) -> tuple[Literal["confirmed", "likely", "unknown"] | None, str]:
    """Classifies losing trades into confirmed, likely, or unknown causes without hallucination."""
    if net_pnl >= 0:
        return (None, "Profitable trade")

    # 1. Confirmed: Objective trigger verified in tick history
    if "STOP_LOSS" in exit_reason or market_context.get("stop_breached"):
        return ("confirmed", "Stop-loss breach confirmed by execution tick price.")

    # 2. Likely: Wide spread or execution anomaly observed
    spread_bps = market_context.get("spread_bps", 0.0)
    if spread_bps > 100.0 or "SLIPPAGE" in exit_reason:
        return ("likely", f"Adverse execution cost: wide spread ({spread_bps:.1f} bps) during trade lifecycle.")

    # 3. Unknown: Normal price action moving against hypothesis without obvious spread/data anomaly
    return ("unknown", f"Standard adverse price drift against strategy hypothesis ({exit_reason}).")


class TelemetryStore:
    """Persistent event and trade ledger backed by SQLite in WAL mode."""

    def __init__(self, db_path: str = "wallex_agent.db") -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
        return self._conn

    def initialize(self) -> None:
        """Initializes database schema tables."""
        conn = self.get_connection()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scanner_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    duration_ms REAL,
                    eligible_count INTEGER,
                    payload_json TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT,
                    strategy_id TEXT,
                    horizon_profile TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    gross_pnl REAL,
                    net_pnl REAL,
                    fee REAL,
                    holding_seconds REAL,
                    opened_at REAL,
                    closed_at REAL,
                    exit_reason TEXT,
                    loss_cause TEXT,
                    post_mortem_notes TEXT
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    total_equity REAL,
                    cash REAL,
                    open_positions_val REAL,
                    mtm_pnl REAL
                );
            """)

    def log_scanner_cycle(
        self,
        cycle_id: str,
        timestamp: float,
        duration_ms: float,
        eligible_count: int,
        candidates: Sequence[Mapping[str, Any]],
    ) -> None:
        conn = self.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO scanner_cycles (cycle_id, timestamp, duration_ms, eligible_count, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cycle_id, timestamp, duration_ms, eligible_count, json.dumps(list(candidates))),
            )

    def log_trade(self, trade: TradeRecord) -> None:
        conn = self.get_connection()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO trades (
                    trade_id, symbol, strategy_id, horizon_profile,
                    entry_price, exit_price, quantity,
                    gross_pnl, net_pnl, fee, holding_seconds,
                    opened_at, closed_at, exit_reason,
                    loss_cause, post_mortem_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade["trade_id"],
                    trade["symbol"],
                    trade["strategy_id"],
                    trade["horizon_profile"],
                    trade["entry_price"],
                    trade["exit_price"],
                    trade["quantity"],
                    trade["gross_realized_pnl_tmn"],
                    trade["net_realized_pnl_tmn"],
                    trade["total_fee_tmn"],
                    trade["holding_seconds"],
                    trade["opened_at"],
                    trade["closed_at"],
                    trade["exit_reason"],
                    trade.get("loss_cause"),
                    trade.get("post_mortem_notes"),
                ),
            )

    def log_equity_snapshot(
        self,
        timestamp: float,
        total_equity: float,
        cash: float,
        open_positions_val: float,
        mtm_pnl: float,
    ) -> None:
        """Stores a time-series equity snapshot for equity curve graphing."""
        conn = self.get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO equity_snapshots (timestamp, total_equity, cash, open_positions_val, mtm_pnl)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, total_equity, cash, open_positions_val, mtm_pnl),
            )

    def get_equity_curve(self, limit: int = 500) -> list[dict[str, Any]]:
        """Retrieves chronological equity curve data points."""
        conn = self.get_connection()
        cursor = conn.execute(
            """
            SELECT timestamp, total_equity, cash, open_positions_val, mtm_pnl
            FROM equity_snapshots
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "timestamp": float(r["timestamp"]),
                "total_equity": float(r["total_equity"]),
                "cash": float(r["cash"]),
                "open_positions_val": float(r["open_positions_val"]),
                "mtm_pnl": float(r["mtm_pnl"]),
            }
            for r in rows
        ]

    def get_recent_trades(self, limit: int = 50) -> list[TradeRecord]:
        conn = self.get_connection()
        cursor = conn.execute(
            """
            SELECT * FROM trades ORDER BY closed_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        trades: list[TradeRecord] = []
        for r in rows:
            trades.append({
                "trade_id": r["trade_id"],
                "symbol": r["symbol"],
                "strategy_id": r["strategy_id"],
                "horizon_profile": r["horizon_profile"],
                "entry_price": r["entry_price"],
                "exit_price": r["exit_price"],
                "quantity": r["quantity"],
                "gross_realized_pnl_tmn": r["gross_pnl"],
                "net_realized_pnl_tmn": r["net_pnl"],
                "total_fee_tmn": r["fee"],
                "holding_seconds": r["holding_seconds"],
                "opened_at": r["opened_at"],
                "closed_at": r["closed_at"],
                "exit_reason": r["exit_reason"],
                "loss_cause": r["loss_cause"],
                "post_mortem_notes": r["post_mortem_notes"],
            })
        return trades

    def get_performance_summary(self) -> dict[str, Any]:
        """Calculates aggregate performance statistics across all recorded trades."""
        trades = self.get_recent_trades(limit=10000)
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "net_realized_pnl_tmn": 0.0,
                "total_fees_tmn": 0.0,
                "total_loss_tmn": 0.0,
                "fee_loss_ratio_pct": 0.0,
                "max_drawdown_pct": 0.0,
            }
        winning = [t for t in trades if t["net_realized_pnl_tmn"] > 0]
        losing = [t for t in trades if t["net_realized_pnl_tmn"] < 0]
        net_pnl = sum(t["net_realized_pnl_tmn"] for t in trades)
        fees = sum(t["total_fee_tmn"] for t in trades)
        total_loss = sum(abs(t["net_realized_pnl_tmn"]) for t in losing)
        fees_on_losing = sum(t["total_fee_tmn"] for t in losing)
        fee_loss_ratio = (fees_on_losing / total_loss * 100.0) if total_loss > 0 else 0.0
        win_rate = (len(winning) / total_trades) * 100.0

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in reversed(trades):
            cumulative += t["net_realized_pnl_tmn"]
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": total_trades,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate_pct": win_rate,
            "net_realized_pnl_tmn": net_pnl,
            "total_fees_tmn": fees,
            "total_loss_tmn": total_loss,
            "fee_loss_ratio_pct": fee_loss_ratio,
            "max_drawdown_pct": (max_dd / 5000000.0) * 100.0 if max_dd > 0 else 0.0,
        }


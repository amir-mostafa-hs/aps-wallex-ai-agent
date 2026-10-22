"""System-level Trading Harness and Simulated Multi-Mode Engine (Primary Testing Seam)."""
from __future__ import annotations
import time
import uuid
from typing import Any, Mapping, Sequence, Literal
from wallex_agent.domain.types import (
    PositionRecord,
    OrderRecord,
    TradeRecord,
    RiskDecision,
    Candidate,
)
from wallex_agent.universe import MarketUniverse
from wallex_agent.scanner import CandidateScanner, AICallBudget
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine, PortfolioState
from wallex_agent.executor import OrderExecutor
from wallex_agent.watchdog import LocalWatchdog
from wallex_agent.telemetry import TelemetryStore, calculate_trade_pnl


class SimulatedExchangeAdapter:
    """Mock exchange adapter for Shadow and Backtest modes with realistic fee/fill mechanics."""

    def __init__(
        self,
        initial_prices: Mapping[str, float] | None = None,
        maker_fee_rate: float = 0.002,
        taker_fee_rate: float = 0.0025,
    ) -> None:
        self.prices: dict[str, float] = dict(initial_prices or {})
        self.maker_fee_rate = maker_fee_rate
        self.taker_fee_rate = taker_fee_rate
        self._order_counter = 1000
        self._orders: dict[str, dict[str, Any]] = {}

    def set_price(self, symbol: str, price: float) -> None:
        self.prices[symbol] = price

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        price: float | None,
        quantity: float,
        client_id: str,
    ) -> dict[str, Any]:
        self._order_counter += 1
        exec_price = price or self.prices.get(symbol, 1.0)
        sum_quote = exec_price * quantity
        fee = sum_quote * self.taker_fee_rate

        order_data = {
            "id": self._order_counter,
            "clientId": client_id,
            "symbol": symbol,
            "side": side,
            "status": "FILLED",
            "executedQty": str(quantity),
            "executedPrice": str(exec_price),
            "executedSum": str(sum_quote),
            "fee": str(fee),
            "fills": [
                {
                    "price": str(exec_price),
                    "quantity": str(quantity),
                    "sum": str(sum_quote),
                    "fee": str(fee),
                    "feeAsset": "TMN" if "TMN" in symbol else "USDT",
                    "timestamp": time.time(),
                }
            ],
        }
        self._orders[client_id] = order_data
        return {"success": True, "result": order_data}

    def get_order(self, client_id: str) -> dict[str, Any]:
        if client_id in self._orders:
            return {"success": True, "result": self._orders[client_id]}
        return {"success": False, "result": None}

    def cancel_order(self, client_id: str) -> dict[str, Any]:
        if client_id in self._orders:
            self._orders[client_id]["status"] = "CANCELLED"
            return {"success": True, "result": self._orders[client_id]}
        return {"success": False, "result": None}


class SystemTradingHarness:
    """Primary system seam integrating all modules across backtest, shadow, and live modes."""

    def __init__(
        self,
        mode: Literal["backtest", "shadow", "live"],
        initial_cash_tmn: float,
        universe: MarketUniverse,
        decision_agent: DecisionAgent,
        risk_engine: RiskEngine,
        telemetry_store: TelemetryStore,
        initial_prices: Mapping[str, float] | None = None,
        exchange_client: Any = None,
    ) -> None:
        self.mode = mode
        self.universe = universe
        self.decision_agent = decision_agent
        self.risk_engine = risk_engine
        self.telemetry = telemetry_store
        if self.telemetry:
            self.telemetry.initialize()
        self.scanner = CandidateScanner()
        self.watchdog = LocalWatchdog()
        self.ai_budget = AICallBudget()
        self.prices: dict[str, float] = dict(initial_prices or {})

        self.initial_cash_tmn = initial_cash_tmn
        self.state: Literal["RUNNING", "PAUSED", "SAFE-STOP"] = "RUNNING"
        self.started_at: float = time.time()
        self.cumulative_fees_tmn: float = 0.0
        self.recent_candidates: list[Candidate] = []
        self.recent_decisions: list[dict[str, Any]] = []
        self.recent_rejections: list[dict[str, Any]] = []

        if exchange_client is None:
            self.exchange_client = SimulatedExchangeAdapter(initial_prices=self.prices)
        else:
            self.exchange_client = exchange_client

        self.executor = OrderExecutor(exchange_client=self.exchange_client)
        self.portfolio: PortfolioState = {
            "total_equity_tmn": initial_cash_tmn,
            "available_cash_tmn": initial_cash_tmn,
            "open_positions": {},
            "open_orders": {},
        }

    def pause(self) -> None:
        """Pauses new entries while maintaining active position management."""
        self.state = "PAUSED"

    def resume(self) -> None:
        """Resumes automated entries."""
        self.state = "RUNNING"

    def flatten(self, reason: str = "MANUAL_FLATTEN") -> list[OrderRecord]:
        """Immediately closes all open positions and enters SAFE-STOP state."""
        orders = self.liquidate_all_positions(reason=reason)
        self.state = "SAFE-STOP"
        return orders

    def run_cycle(
        self,
        market_snapshot: Mapping[str, Mapping[str, Any]],
        timestamp: float,
    ) -> dict[str, Any]:
        """Runs a complete trading cycle through public interface boundaries."""
        cycle_id = f"cyc-{uuid.uuid4().hex[:8]}"

        # 1. Update prices in local memory
        for sym, data in market_snapshot.items():
            if "current_price" in data:
                self.prices[sym] = float(data["current_price"])
                if isinstance(self.exchange_client, SimulatedExchangeAdapter):
                    self.exchange_client.set_price(sym, float(data["current_price"]))

        # 2. Watchdog evaluation of active positions
        triggers = self.watchdog.check_all(
            positions=list(self.portfolio["open_positions"].values()),
            prices=self.prices,
            current_time=timestamp,
        )

        orders_submitted = 0
        for trigger in triggers:
            sym = trigger["symbol"]
            qty = trigger["position_quantity"]
            price = self.prices.get(sym, 1.0)
            prec = self.universe.get_precision(sym) or (4, 0)

            exit_decision: RiskDecision = {
                "approved": True,
                "intent_id": f"exit-{trigger['trigger_type']}",
                "symbol": sym,
                "action": "EXIT",
                "approved_quantity": qty,
                "approved_notional": qty * price,
                "projected_stop_price": None,
                "projected_take_profit_price": None,
                "reject_code": None,
                "rejection_reason": None,
            }

            order = self.executor.submit_order(exit_decision, price=price, price_precision=prec[1], amount_precision=prec[0])
            orders_submitted += 1
            self._handle_fill(order, exit_reason=trigger["trigger_type"])

        # If state is PAUSED or SAFE-STOP, do not scan new candidates or open new positions
        if self.state in ("PAUSED", "SAFE-STOP"):
            self._update_equity()
            return {
                "cycle_id": cycle_id,
                "orders_submitted": orders_submitted,
                "total_equity": self.portfolio["total_equity_tmn"],
                "available_cash": self.portfolio["available_cash_tmn"],
                "open_positions_count": len(self.portfolio["open_positions"]),
                "state": self.state,
            }

        # 3. Scan candidates from market snapshot
        candidates: list[Candidate] = []
        for sym, data in market_snapshot.items():
            if not self.universe.is_allowed(sym):
                continue
            cand = self.scanner.evaluate_candidate(
                symbol=sym,
                features=data.get("features", {}),
                spread_bps=data.get("spread_bps", 20.0),
                is_stale=data.get("is_stale", False),
            )
            candidates.append(cand)

        ranked = self.scanner.rank_candidates(candidates, top_k=3)
        self.recent_candidates = ranked

        # 4. Evaluate top candidate with DecisionAgent if AI budget allows
        if ranked and self.ai_budget.can_call(timestamp):
            top = ranked[0]
            context = {
                "symbol": top["symbol"],
                "cycle_id": cycle_id,
                "features": top["features"],
                "spread_bps": top.get("estimated_cost_bps", 20.0),
                "evidence_ids": market_snapshot[top["symbol"]].get("evidence_ids", []),
                "has_open_position": top["symbol"] in self.portfolio["open_positions"],
            }
            intent = self.decision_agent.decide(context)
            self.ai_budget.record_call(timestamp)
            self.recent_decisions.append({
                "symbol": top["symbol"],
                "action": intent["action"],
                "confidence": intent.get("confidence", 0.0),
                "rationale": intent.get("decision_rationale", ""),
                "timestamp": timestamp,
            })
            self.recent_decisions = self.recent_decisions[-20:]

            # 5. Risk Engine evaluates intent
            curr_price = self.prices.get(top["symbol"], 1.0)
            decision = self.risk_engine.evaluate(intent, self.portfolio, current_price=curr_price)

            if not decision["approved"]:
                self.recent_rejections.append({
                    "symbol": top["symbol"],
                    "reject_code": decision.get("reject_code"),
                    "reason": decision.get("rejection_reason"),
                    "timestamp": timestamp,
                })
                self.recent_rejections = self.recent_rejections[-20:]

            # 6. Execute if approved
            if decision["approved"]:
                prec = self.universe.get_precision(top["symbol"]) or (4, 0)
                order = self.executor.submit_order(
                    decision=decision,
                    price=curr_price,
                    price_precision=prec[1],
                    amount_precision=prec[0],
                )
                orders_submitted += 1
                self._handle_fill(order)

        # 7. Update portfolio equity
        self._update_equity()

        return {
            "cycle_id": cycle_id,
            "orders_submitted": orders_submitted,
            "total_equity": self.portfolio["total_equity_tmn"],
            "available_cash": self.portfolio["available_cash_tmn"],
            "open_positions_count": len(self.portfolio["open_positions"]),
        }

    def liquidate_all_positions(self, reason: str = "END_OF_CONTEST") -> list[OrderRecord]:
        """Liquidates 100% of open coin positions into TMN."""
        orders: list[OrderRecord] = []
        open_syms = list(self.portfolio["open_positions"].keys())

        for sym in open_syms:
            pos = self.portfolio["open_positions"][sym]
            price = self.prices.get(sym, pos["current_price"])
            prec = self.universe.get_precision(sym) or (4, 0)

            decision: RiskDecision = {
                "approved": True,
                "intent_id": f"liq-{sym}",
                "symbol": sym,
                "action": "EXIT",
                "approved_quantity": pos["quantity"],
                "approved_notional": pos["quantity"] * price,
                "projected_stop_price": None,
                "projected_take_profit_price": None,
                "reject_code": None,
                "rejection_reason": reason,
            }
            order = self.executor.submit_order(decision, price=price, price_precision=prec[1], amount_precision=prec[0])
            orders.append(order)
            self._handle_fill(order, exit_reason=reason)

        self._update_equity()
        return orders

    def _handle_fill(self, order: OrderRecord, exit_reason: str = "NORMAL_EXIT") -> None:
        """Processes order fills into portfolio positions and records trades."""
        if order["status"] not in ("FILLED", "PARTIALLY_FILLED"):
            return

        sym = order["symbol"]
        qty = float(order["executed_qty"]) if float(order["executed_qty"]) > 0 else float(order["quantity"])
        price = float(order["price"]) if order["price"] else 1.0
        fee = float(order["cumulative_fee"])
        self.cumulative_fees_tmn += fee

        if order["side"] == "BUY":
            cost = (qty * price) + fee
            self.portfolio["available_cash_tmn"] -= cost
            self.portfolio["open_positions"][sym] = {
                "position_id": f"pos-{order['client_id']}",
                "symbol": sym,
                "quantity": qty,
                "entry_price": price,
                "current_price": price,
                "unrealized_pnl_tmn": 0.0,
                "realized_pnl_tmn": 0.0,
                "cumulative_fee_tmn": fee,
                "stop_price": price * 0.99,  # Default 1%
                "take_profit_price": price * 1.02,
                "opened_at": order["created_at"],
                "max_holding_seconds": 300.0,
                "is_open": True,
            }
        elif order["side"] == "SELL":
            proceeds = (qty * price) - fee
            self.portfolio["available_cash_tmn"] += proceeds

            pos = self.portfolio["open_positions"].pop(sym, None)
            if pos:
                gross_pnl, net_pnl = calculate_trade_pnl(
                    entry_price=pos["entry_price"],
                    exit_price=price,
                    quantity=qty,
                    entry_fee=pos["cumulative_fee_tmn"],
                    exit_fee=fee,
                )
                trade: TradeRecord = {
                    "trade_id": f"tr-{order['client_id']}",
                    "symbol": sym,
                    "strategy_id": "momentum",
                    "horizon_profile": "FAST",
                    "entry_price": pos["entry_price"],
                    "exit_price": price,
                    "quantity": qty,
                    "net_realized_pnl_tmn": net_pnl,
                    "gross_realized_pnl_tmn": gross_pnl,
                    "total_fee_tmn": pos["cumulative_fee_tmn"] + fee,
                    "holding_seconds": order["created_at"] - pos["opened_at"],
                    "opened_at": pos["opened_at"],
                    "closed_at": order["created_at"],
                    "exit_reason": exit_reason,
                    "loss_cause": "confirmed" if net_pnl < 0 else None,
                    "post_mortem_notes": f"Exit triggered: {exit_reason}",
                }
                self.telemetry.log_trade(trade)

    def _update_equity(self) -> None:
        """Recalculates mark-to-market equity."""
        pos_val = sum(
            p["quantity"] * self.prices.get(p["symbol"], p["current_price"])
            for p in self.portfolio["open_positions"].values()
        )
        self.portfolio["total_equity_tmn"] = self.portfolio["available_cash_tmn"] + pos_val

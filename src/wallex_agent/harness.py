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
from wallex_agent.scanner import CandidateScanner, AICallBudget, ReviewPriorityQueue, ReviewItem
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine, PortfolioState
from wallex_agent.executor import OrderExecutor, ShadowOrderExecutor
from wallex_agent.watchdog import LocalWatchdog
from wallex_agent.telemetry import TelemetryStore, calculate_trade_pnl, classify_loss_cause


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
        max_execution_quote_age_seconds: float = 5.0,
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
        self.max_execution_quote_age_seconds = max_execution_quote_age_seconds

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

        if self.mode in ("shadow", "backtest"):
            self.executor = ShadowOrderExecutor()
        else:
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

        # 4. Enqueue into ReviewPriorityQueue (open positions nearing limits take precedence)
        queue = ReviewPriorityQueue()

        for sym, pos in self.portfolio["open_positions"].items():
            if not pos.get("is_open", True):
                continue
            time_held = timestamp - pos.get("opened_at", timestamp)
            max_holding = pos.get("max_holding_seconds", 300.0)
            time_ratio = (time_held / max_holding) if max_holding > 0 else 0.0

            curr_price = self.prices.get(sym, pos.get("current_price", 1.0))
            entry_price = pos.get("entry_price", curr_price)
            stop_price = pos.get("stop_price")

            initial_stop_dist = entry_price - stop_price if (stop_price and entry_price > stop_price) else 0.0
            current_stop_dist = curr_price - stop_price if (stop_price and curr_price > stop_price) else 0.0
            loss_dist_ratio = (current_stop_dist / initial_stop_dist) if initial_stop_dist > 0 else 1.0

            # High priority if held >= 70% of max time or remaining stop distance <= 30% of initial buffer
            if time_ratio >= 0.7 or (loss_dist_ratio <= 0.3 and initial_stop_dist > 0):
                urgency = 50.0 + max(time_ratio * 40.0, max(0.0, (1.0 - loss_dist_ratio) * 40.0))
                queue.push(
                    ReviewItem(
                        item_type="POSITION",
                        symbol=sym,
                        priority=urgency,
                        context=dict(pos),
                    )
                )

        # Enqueue top candidates
        for cand in ranked:
            queue.push(
                ReviewItem(
                    item_type="CANDIDATE",
                    symbol=cand["symbol"],
                    priority=cand["score"],
                    context=dict(cand),
                )
            )

        # 5. Evaluate highest priority item if AI budget allows
        if len(queue) > 0 and self.ai_budget.can_call(timestamp):
            top_item = queue.pop()
            if top_item is not None and top_item.item_type == "POSITION":
                sym = top_item.symbol
                pos = top_item.context
                context = {
                    "symbol": sym,
                    "cycle_id": cycle_id,
                    "action_hint": "POSITION_REVIEW",
                    "features": market_snapshot.get(sym, {}).get("features", {}),
                    "spread_bps": market_snapshot.get(sym, {}).get("spread_bps", 20.0),
                    "evidence_ids": market_snapshot.get(sym, {}).get("evidence_ids", []),
                    "has_open_position": True,
                    "position": pos,
                }
                intent = self.decision_agent.decide(context)
                self.ai_budget.record_call(timestamp)
                self.recent_decisions.append({
                    "symbol": sym,
                    "action": intent["action"],
                    "confidence": intent.get("confidence", 0.0),
                    "rationale": intent.get("decision_rationale", ""),
                    "timestamp": timestamp,
                })
                self.recent_decisions = self.recent_decisions[-20:]

                if intent["action"] == "EXIT":
                    curr_price = self.prices.get(sym, pos.get("current_price", 1.0))
                    decision = self.risk_engine.evaluate(intent, self.portfolio, current_price=curr_price)
                    if decision["approved"]:
                        prec = self.universe.get_precision(sym) or (4, 0)
                        order = self.executor.submit_order(
                            decision=decision,
                            price=curr_price,
                            price_precision=prec[1],
                            amount_precision=prec[0],
                        )
                        orders_submitted += 1
                        self._handle_fill(order, exit_reason="AGENT_EXIT", decision=decision, intent=intent)
            elif top_item is not None and top_item.item_type == "CANDIDATE":
                top_sym = top_item.symbol
                cand_ctx = top_item.context
                context = {
                    "symbol": top_sym,
                    "cycle_id": cycle_id,
                    "features": cand_ctx.get("features", {}),
                    "spread_bps": cand_ctx.get("estimated_cost_bps", 20.0),
                    "evidence_ids": market_snapshot.get(top_sym, {}).get("evidence_ids", []),
                    "has_open_position": top_sym in self.portfolio["open_positions"],
                }
                intent = self.decision_agent.decide(context)
                self.ai_budget.record_call(timestamp)
                self.recent_decisions.append({
                    "symbol": top_sym,
                    "action": intent["action"],
                    "confidence": intent.get("confidence", 0.0),
                    "rationale": intent.get("decision_rationale", ""),
                    "timestamp": timestamp,
                })
                self.recent_decisions = self.recent_decisions[-20:]

                # Risk Engine evaluates intent
                curr_price = self.prices.get(top_sym, 1.0)
                decision = self.risk_engine.evaluate(intent, self.portfolio, current_price=curr_price)

                if not decision["approved"]:
                    self.recent_rejections.append({
                        "symbol": top_sym,
                        "reject_code": decision.get("reject_code"),
                        "reason": decision.get("rejection_reason"),
                        "timestamp": timestamp,
                    })
                    self.recent_rejections = self.recent_rejections[-20:]

                # Execute if approved
                if decision["approved"]:
                    # Re-validate execution quote freshness (5s freshness requirement)
                    quote_ts = float(market_snapshot[top_sym].get("quote_timestamp", timestamp))
                    quote_age = timestamp - quote_ts
                    if quote_age > self.max_execution_quote_age_seconds:
                        self.recent_rejections.append({
                            "symbol": top_sym,
                            "reject_code": "STALE_DATA",
                            "reason": f"Execution quote age {quote_age:.1f}s exceeded threshold {self.max_execution_quote_age_seconds}s",
                            "timestamp": timestamp,
                        })
                        self.recent_rejections = self.recent_rejections[-20:]
                    else:
                        prec = self.universe.get_precision(top_sym) or (4, 0)
                        order = self.executor.submit_order(
                            decision=decision,
                            price=curr_price,
                            price_precision=prec[1],
                            amount_precision=prec[0],
                        )
                        orders_submitted += 1
                        self._handle_fill(order, decision=decision, intent=intent)

        # 7. Update portfolio equity
        self._update_equity(timestamp=timestamp)

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

    def _handle_fill(
        self,
        order: OrderRecord,
        exit_reason: str = "NORMAL_EXIT",
        decision: RiskDecision | None = None,
        intent: TradeIntent | None = None,
    ) -> None:
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

            # Dynamic stop and take-profit from decision, with conservative fallbacks
            stop_price = (decision.get("projected_stop_price") if decision else None) or (price * 0.99)
            take_profit_price = (decision.get("projected_take_profit_price") if decision else None) or (price * 1.02)
            max_holding_seconds = (float(intent["max_holding_minutes"]) * 60.0) if (intent and intent.get("max_holding_minutes")) else 300.0
            strat_id = (intent.get("strategy_id") if intent else "momentum") or "momentum"
            entry_rationale = (intent.get("decision_rationale") if intent else "") or ""
            evidence_ids = list(intent.get("evidence_ids", [])) if intent else []

            self.portfolio["open_positions"][sym] = {
                "position_id": f"pos-{order['client_id']}",
                "symbol": sym,
                "strategy_id": strat_id,
                "quantity": qty,
                "entry_price": price,
                "current_price": price,
                "unrealized_pnl_tmn": 0.0,
                "realized_pnl_tmn": 0.0,
                "cumulative_fee_tmn": fee,
                "stop_price": stop_price,
                "take_profit_price": take_profit_price,
                "opened_at": order["created_at"],
                "max_holding_seconds": max_holding_seconds,
                "is_open": True,
                "entry_rationale": entry_rationale,
                "evidence_ids": evidence_ids,
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
                loss_cause, cause_desc = classify_loss_cause(
                    exit_reason=exit_reason,
                    net_pnl=net_pnl,
                    market_context={"spread_bps": 15.0, "stop_breached": "STOP" in exit_reason},
                )
                entry_rat = pos.get("entry_rationale", "")
                ev_ids = pos.get("evidence_ids", [])
                post_mortem = (
                    f"{cause_desc} | Rationale: {entry_rat} | Evidence: {','.join(ev_ids)}"
                    if net_pnl < 0
                    else f"Target achieved: {exit_reason}"
                )
                trade: TradeRecord = {
                    "trade_id": f"tr-{order['client_id']}",
                    "symbol": sym,
                    "strategy_id": pos.get("strategy_id", "momentum"),
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
                    "loss_cause": loss_cause,
                    "post_mortem_notes": post_mortem,
                }
                self.telemetry.log_trade(trade)

    def _update_equity(self, timestamp: float | None = None) -> None:
        """Recalculates mark-to-market equity and logs snapshot if telemetry configured."""
        pos_val = sum(
            p["quantity"] * self.prices.get(p["symbol"], p["current_price"])
            for p in self.portfolio["open_positions"].values()
        )
        self.portfolio["total_equity_tmn"] = self.portfolio["available_cash_tmn"] + pos_val
        if timestamp is not None and getattr(self, "telemetry", None):
            cost_basis = sum(p["quantity"] * p["entry_price"] for p in self.portfolio["open_positions"].values())
            self.telemetry.log_equity_snapshot(
                timestamp=timestamp,
                total_equity=self.portfolio["total_equity_tmn"],
                cash=self.portfolio["available_cash_tmn"],
                open_positions_val=pos_val,
                mtm_pnl=pos_val - cost_basis,
            )



def run_simulation_backtest(
    cycles: int = 50,
    initial_cash_tmn: float = 5000000.0,
    heuristic_mode: bool = True,
    telemetry_db_path: str = ":memory:",
    strategy_id: str = "momentum",
    stop_distance_pct: float = 1.0,
    take_profit_distance_pct: float = 2.0,
    max_holding_minutes: int = 5,
) -> dict[str, Any]:
    """Executes a standardized multi-scenario simulated backtest."""
    telemetry = TelemetryStore(db_path=telemetry_db_path)
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

    decision_agent = DecisionAgent(
        heuristic_mode=heuristic_mode,
        default_strategy=strategy_id,
        default_stop_pct=stop_distance_pct,
        default_take_profit_pct=take_profit_distance_pct,
        default_max_holding_minutes=max_holding_minutes,
    )

    harness = SystemTradingHarness(
        mode="backtest",
        initial_cash_tmn=initial_cash_tmn,
        universe=universe,
        decision_agent=decision_agent,
        risk_engine=RiskEngine(
            risk_per_trade_equity_pct=0.005,
            max_position_notional_equity_pct=0.15,
            min_notional_tmn=100000.0,
        ),
        telemetry_store=telemetry,
        initial_prices={"BTCTMN": 4500000000.0, "ETHTMN": 250000000.0, "USDTTMN": 70000.0},
    )

    base_prices = {"BTCTMN": 4500000000.0, "ETHTMN": 250000000.0, "USDTTMN": 70000.0}

    for cycle in range(cycles):
        t = 1000.0 + (cycle * 15.0)
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

    harness.liquidate_all_positions(reason="END_OF_BACKTEST")
    summary = telemetry.get_performance_summary()
    trades = telemetry.get_recent_trades(limit=100)
    final_equity = harness.portfolio["total_equity_tmn"]
    net_pnl = final_equity - initial_cash_tmn
    roi_pct = (net_pnl / initial_cash_tmn) * 100
    gross_pnl = sum(float(t.get("gross_realized_pnl_tmn", 0.0)) for t in trades)
    total_fees = float(harness.cumulative_fees_tmn)
    equity_curve = telemetry.get_equity_curve()

    return {
        "run_id": f"bt-{uuid.uuid4().hex[:8]}",
        "harness": harness,
        "telemetry": telemetry,
        "initial_capital_tmn": initial_cash_tmn,
        "final_equity_tmn": final_equity,
        "gross_pnl_tmn": gross_pnl,
        "total_fees_tmn": total_fees,
        "net_pnl_tmn": net_pnl,
        "roi_pct": roi_pct,
        "strategy_id": strategy_id,
        "stop_distance_pct": stop_distance_pct,
        "take_profit_distance_pct": take_profit_distance_pct,
        "max_holding_minutes": max_holding_minutes,
        "summary": summary,
        "trades": trades,
        "equity_curve": equity_curve,
    }


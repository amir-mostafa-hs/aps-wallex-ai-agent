"""Domain types for Wallex Opportunity Agent.

Strict constraint: Uses typing.TypedDict only. Zero Pydantic models.
"""
from __future__ import annotations
from typing import TypedDict, Literal, NotRequired, Sequence, Mapping, Any

# Canonical Enums as Literals
Action = Literal["NO_TRADE", "BUY", "HOLD", "EXIT"]
StrategyId = Literal["momentum", "trend_following", "mean_reversion", "trend_filtered_pullback"]
HorizonProfile = Literal["FAST", "INTRADAY_SHORT", "INTRADAY"]
ReasonCode = Literal[
    "EDGE_INSUFFICIENT",
    "SIGNAL_VALID",
    "SIGNAL_INVALIDATED",
    "RISK_CONTEXT",
    "DATA_UNCERTAIN",
    "OTHER",
]
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT", "MARKET", "STOP_LIMIT", "STOP_MARKET"]
OrderStatus = Literal[
    "CREATED",
    "SUBMITTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELLED",
    "REJECTED",
    "UNKNOWN",
]
RiskRejectCode = Literal[
    "INVALID_INTENT",
    "STALE_DATA",
    "EXPOSURE_CAP",
    "POSITION_LIMIT",
    "INSUFFICIENT_CASH",
    "NEGATIVE_EDGE",
    "LIQUIDATION_RISK",
    "UNVERIFIED_NOTIONAL",
    "ACCOUNT_MISMATCH",
]


class TradeIntent(TypedDict):
    contract_version: str
    decision_id: str
    cycle_id: str
    symbol: str
    action: Action
    strategy_id: StrategyId | None
    horizon_profile: HorizonProfile | None
    confidence: float
    reason_code: ReasonCode
    decision_rationale: str
    invalidation_condition: str | None
    stop_distance_pct: float | None
    take_profit_distance_pct: float | None
    max_holding_minutes: int | None
    parameter_overrides: Mapping[str, Any]
    evidence_ids: Sequence[str]


class MarketInfo(TypedDict):
    symbol: str
    base_asset: str
    quote_asset: str
    is_spot: bool
    is_active: bool
    is_tmn_based: bool
    is_usdt_based: bool
    amount_precision: int
    price_precision: int
    min_quantity: float | None
    min_notional: float | None


class Candle(TypedDict):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketSnapshot(TypedDict):
    symbol: str
    timestamp: float
    bid_price: float
    ask_price: float
    last_price: float
    spread_bps: float
    volume_24h: float
    is_stale: bool
    candles: Mapping[str, Sequence[Candle]]  # resolution -> candles


class Candidate(TypedDict):
    symbol: str
    score: float
    features: Mapping[str, float]
    estimated_cost_bps: float
    is_eligible: bool
    exclusion_reason: str | None


class RiskDecision(TypedDict):
    approved: bool
    intent_id: str
    symbol: str
    action: Action
    approved_quantity: float
    approved_notional: float
    projected_stop_price: float | None
    projected_take_profit_price: float | None
    reject_code: RiskRejectCode | None
    rejection_reason: str | None


class OrderFill(TypedDict):
    fill_id: str
    price: float
    quantity: float
    sum_quote: float
    fee: float
    fee_asset: str
    timestamp: float


class OrderRecord(TypedDict):
    client_id: str
    exchange_order_id: str | None
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float | None
    quantity: float
    status: OrderStatus
    executed_qty: float
    executed_sum: float
    cumulative_fee: float
    created_at: float
    updated_at: float
    fills: Sequence[OrderFill]


class PositionRecord(TypedDict):
    position_id: str
    symbol: str
    strategy_id: NotRequired[StrategyId | None]
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl_tmn: float
    realized_pnl_tmn: float
    cumulative_fee_tmn: float
    stop_price: float
    take_profit_price: float | None
    opened_at: float
    max_holding_seconds: float
    is_open: bool
    entry_rationale: NotRequired[str | None]
    evidence_ids: NotRequired[Sequence[str]]




class TradeRecord(TypedDict):
    trade_id: str
    symbol: str
    strategy_id: StrategyId | None
    horizon_profile: HorizonProfile | None
    entry_price: float
    exit_price: float
    quantity: float
    net_realized_pnl_tmn: float
    gross_realized_pnl_tmn: float
    total_fee_tmn: float
    holding_seconds: float
    opened_at: float
    closed_at: float
    exit_reason: str
    loss_cause: Literal["confirmed", "likely", "unknown"] | None
    post_mortem_notes: str | None

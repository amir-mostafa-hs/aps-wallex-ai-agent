"""Authoritative Wallex Market Data Adapter (Ticket 23).

Queries official Wallex market endpoints, validates live prices and precisions,
calculates spreads and staleness, and eliminates hardcoded price fallbacks.
"""
from __future__ import annotations
import math
import time
from typing import TypedDict, Mapping, Any
import httpx
from wallex_agent.features import calculate_spread_bps


class MarketDataError(RuntimeError):
    """Raised when market data retrieval or validation fails."""
    pass


class LiveMarketSnapshot(TypedDict):
    symbol: str
    base_asset: str
    quote_asset: str
    last_price: float
    bid_price: float
    ask_price: float
    spread_bps: float
    volume_24h: float
    change_24h_pct: float
    min_notional: float
    min_qty: float
    price_precision: int
    amount_precision: int
    timestamp: float
    is_stale: bool
    quote_timestamp: float


def _parse_positive_finite(val: Any) -> float | None:
    try:
        f = float(val)
        if math.isfinite(f) and f > 0.0:
            return f
    except (ValueError, TypeError):
        pass
    return None


class WallexMarketDataAdapter:
    """Consolidated market data provider communicating with official Wallex endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.wallex.ir",
        http_client: Any = None,
        max_age_seconds: float = 15.0,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=timeout)
        self.max_age_seconds = max_age_seconds
        self._cache: dict[str, LiveMarketSnapshot] = {}
        self._last_refresh_timestamp: float = 0.0

    def refresh_all_markets(self) -> dict[str, LiveMarketSnapshot]:
        """Polls GET /v1/markets, parses symbols, and stores validated live snapshots."""
        url = f"{self.base_url}/v1/markets"
        now = time.time()

        try:
            resp = self.http_client.get(url)
            if resp.status_code != 200:
                raise MarketDataError(f"Wallex markets API returned HTTP {resp.status_code}")
            data = resp.json()
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError(f"Network error querying Wallex markets: {exc}") from exc

        symbols_dict = data.get("result", {}).get("symbols", {})
        if not symbols_dict:
            raise MarketDataError("Wallex markets API returned empty symbols payload.")

        new_snapshots: dict[str, LiveMarketSnapshot] = {}

        for sym, item in symbols_dict.items():
            sym_clean = str(item.get("symbol") or sym).strip().upper()
            base_asset = str(item.get("baseAsset") or "").strip().upper()
            quote_asset = str(item.get("quoteAsset") or "").strip().upper()

            stats = item.get("stats", {})
            last_p = _parse_positive_finite(stats.get("lastPrice"))
            bid_p = _parse_positive_finite(stats.get("bidPrice")) or last_p
            ask_p = _parse_positive_finite(stats.get("askPrice")) or last_p

            if last_p is None or bid_p is None or ask_p is None:
                # Reject malformed or non-positive price records
                continue

            spread_bps = calculate_spread_bps(bid_p, ask_p)
            vol_24h = _parse_positive_finite(stats.get("24h_volume")) or 0.0
            ch_24h = float(stats.get("24h_ch", 0.0))
            min_notional = float(item.get("minNotional") or 100000.0)
            min_qty = float(item.get("minQty") or 0.0)
            amount_precision = int(item.get("stepSize") or item.get("baseAssetPrecision") or 6)
            price_precision = int(item.get("tickSize") or item.get("quotePrecision") or 0)

            snap: LiveMarketSnapshot = {
                "symbol": sym_clean,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "last_price": last_p,
                "bid_price": bid_p,
                "ask_price": ask_p,
                "spread_bps": spread_bps,
                "volume_24h": vol_24h,
                "change_24h_pct": ch_24h,
                "min_notional": min_notional,
                "min_qty": min_qty,
                "price_precision": price_precision,
                "amount_precision": amount_precision,
                "timestamp": now,
                "is_stale": False,
                "quote_timestamp": now,
            }
            new_snapshots[sym_clean] = snap

        self._cache = new_snapshots
        self._last_refresh_timestamp = now
        return self._cache

    def get_snapshot(self, symbol: str) -> LiveMarketSnapshot | None:
        """Returns snapshot for symbol, refreshing if cache is empty or stale."""
        now = time.time()
        if not self._cache or (now - self._last_refresh_timestamp) > self.max_age_seconds:
            try:
                self.refresh_all_markets()
            except MarketDataError:
                pass

        snap = self._cache.get(symbol.strip().upper())
        if snap is not None:
            # Recheck staleness dynamically
            is_stale = (now - snap["timestamp"]) > self.max_age_seconds
            snap["is_stale"] = is_stale
        return snap

    def get_usdttmn_rate(self) -> float:
        """Returns the live validated USDTTMN market rate."""
        snap = self.get_snapshot("USDTTMN")
        if snap is None:
            self.refresh_all_markets()
            snap = self._cache.get("USDTTMN")

        if snap is None or snap.get("last_price") is None:
            raise MarketDataError("Live USDTTMN market rate is unavailable from Wallex API.")

        return float(snap["last_price"])

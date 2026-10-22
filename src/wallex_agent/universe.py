"""Market Universe manager and Fail-Closed allowlist builder."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Mapping, Sequence, Set
from wallex_agent.domain.types import MarketInfo
from wallex_agent.domain.validation import validate_market_info


class UniverseError(Exception):
    """Raised when market universe cannot be safely computed."""
    pass


def normalize_symbol(symbol: str) -> str:
    """Normalizes exchange symbol by stripping whitespace, removing '/', and uppercasing."""
    if not symbol:
        return ""
    return symbol.strip().replace("/", "").upper()


class MarketUniverse:
    """Immutable collection of tradeable Spot markets for Wallex Opportunity Agent."""

    def __init__(self, allowlist: Sequence[MarketInfo], union_denylist: Set[str]) -> None:
        self._allowlist: list[MarketInfo] = list(allowlist)
        self._by_symbol: dict[str, MarketInfo] = {m["symbol"]: m for m in allowlist}
        self._union_denylist: Set[str] = set(union_denylist)

    @classmethod
    def build(
        cls,
        markets: Sequence[Mapping[str, Any]],
        local_denylist: Sequence[str],
        package_unavailable: Sequence[str],
    ) -> MarketUniverse:
        """Computes the allowlist by merging local denylist with package unavailable markets.
        
        Enforces Fail-Closed policy: if local_denylist is empty or unreviewed, raises UniverseError.
        """
        if not local_denylist or len(local_denylist) == 0:
            raise UniverseError(
                "Fail-Closed: local denylist (derived from assets.md) is missing or empty. "
                "Live trading and allowlist calculation are prohibited."
            )

        # 1. Normalize both denylists
        normalized_local: Set[str] = {
            normalize_symbol(s) for s in local_denylist if s and normalize_symbol(s)
        }
        normalized_package: Set[str] = {
            normalize_symbol(s) for s in package_unavailable if s and normalize_symbol(s)
        }
        union_denylist: Set[str] = normalized_local.union(normalized_package)

        # 2. Filter markets
        allowed_markets: list[MarketInfo] = []
        for raw in markets:
            norm_sym = normalize_symbol(str(raw.get("symbol", "")))
            if not norm_sym:
                continue

            # Check spot and active flags
            is_spot = bool(raw.get("is_spot", False))
            is_active = bool(raw.get("is_active", True))

            if not is_spot or not is_active:
                continue

            # Must not be in union denylist
            if norm_sym in union_denylist:
                continue

            market_data = dict(raw)
            market_data["symbol"] = norm_sym
            validated = validate_market_info(market_data)
            allowed_markets.append(validated)

        return cls(allowlist=allowed_markets, union_denylist=union_denylist)

    @classmethod
    def from_files(
        cls,
        markets_data: Sequence[Mapping[str, Any]],
        local_denylist_path: str | Path,
        package_data: Mapping[str, Any] | Sequence[str] | None = None,
    ) -> MarketUniverse:
        """Loads denylists from disk and computes universe."""
        denylist_path = Path(local_denylist_path)
        if not denylist_path.exists():
            raise UniverseError(f"Local denylist file not found at: {denylist_path}")

        with open(denylist_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if isinstance(raw_data, dict):
            local_list = raw_data.get("inactive_markets", [])
        elif isinstance(raw_data, list):
            local_list = raw_data
        else:
            raise UniverseError(f"Unexpected JSON format in {denylist_path}: {type(raw_data).__name__}")

        package_unavailable: list[str] = []
        if package_data:
            if isinstance(package_data, Mapping):
                # e.g. GET /v1/prop/packages/183 response
                pkg_result = package_data.get("result", package_data)
                package_unavailable = list(pkg_result.get("unavailableMarkets", []))
            elif isinstance(package_data, Sequence):
                package_unavailable = list(package_data)

        return cls.build(
            markets=markets_data,
            local_denylist=local_list,
            package_unavailable=package_unavailable,
        )

    def get_allowlist(self) -> list[MarketInfo]:
        """Returns a copy of the allowed market list."""
        return list(self._allowlist)

    def is_allowed(self, symbol: str) -> bool:
        """Checks if a normalized symbol is tradeable in this universe."""
        return normalize_symbol(symbol) in self._by_symbol

    def get_market_info(self, symbol: str) -> MarketInfo | None:
        """Returns MarketInfo for symbol, or None if disallowed."""
        return self._by_symbol.get(normalize_symbol(symbol))

    def get_precision(self, symbol: str) -> tuple[int, int] | None:
        """Returns (amount_precision, price_precision) for symbol, or None if disallowed."""
        info = self.get_market_info(symbol)
        if info is None:
            return None
        return (info["amount_precision"], info["price_precision"])

    @property
    def allowed_symbols(self) -> list[str]:
        """Returns the list of allowed symbol strings."""
        return list(self._by_symbol.keys())

    @property
    def total_count(self) -> int:
        return len(self._allowlist)


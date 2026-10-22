import pytest
from pathlib import Path
from wallex_agent.domain.types import MarketInfo
from wallex_agent.universe import MarketUniverse, normalize_symbol, UniverseError


def test_normalize_symbol():
    assert normalize_symbol("BTC/TMN") == "BTCTMN"
    assert normalize_symbol("usdt_tmn") == "USDT_TMN"
    assert normalize_symbol(" ETHUSDT ") == "ETHUSDT"
    assert normalize_symbol("1INCH/TMN") == "1INCHTMN"


def test_build_market_universe_filters_inactive_and_denylisted():
    raw_markets = [
        {
            "symbol": "BTCTMN",
            "base_asset": "BTC",
            "quote_asset": "TMN",
            "is_spot": True,
            "is_active": True,
            "is_tmn_based": True,
            "is_usdt_based": False,
            "amount_precision": 8,
            "price_precision": 0,
        },
        {
            "symbol": "ATMN",  # In local denylist
            "base_asset": "A",
            "quote_asset": "TMN",
            "is_spot": True,
            "is_active": True,
            "is_tmn_based": True,
            "is_usdt_based": False,
            "amount_precision": 2,
            "price_precision": 0,
        },
        {
            "symbol": "OMTMN",  # In package unavailable markets
            "base_asset": "OM",
            "quote_asset": "TMN",
            "is_spot": True,
            "is_active": True,
            "is_tmn_based": True,
            "is_usdt_based": False,
            "amount_precision": 2,
            "price_precision": 0,
        },
        {
            "symbol": "FUTURES_PAIR",
            "base_asset": "FP",
            "quote_asset": "TMN",
            "is_spot": False,  # Not Spot!
            "is_active": True,
            "is_tmn_based": True,
            "is_usdt_based": False,
            "amount_precision": 2,
            "price_precision": 0,
        },
    ]
    local_denylist = ["A/TMN", "B/TMN"]
    package_unavailable = ["OMTMN", "BALTMN"]

    universe = MarketUniverse.build(
        markets=raw_markets,
        local_denylist=local_denylist,
        package_unavailable=package_unavailable,
    )

    allowlist = universe.get_allowlist()
    assert len(allowlist) == 1
    assert allowlist[0]["symbol"] == "BTCTMN"
    assert universe.is_allowed("BTCTMN") is True
    assert universe.is_allowed("ATMN") is False
    assert universe.is_allowed("OMTMN") is False
    assert universe.is_allowed("FUTURES_PAIR") is False


def test_fail_closed_on_empty_or_missing_denylist():
    raw_markets = [{"symbol": "BTCTMN", "is_spot": True, "is_active": True}]
    # Empty denylist must fail closed!
    with pytest.raises(UniverseError, match="denylist"):
        MarketUniverse.build(
            markets=raw_markets,
            local_denylist=[],
            package_unavailable=["OMTMN"],
        )


def test_precision_retrieval():
    raw_markets = [
        {
            "symbol": "BTCTMN",
            "base_asset": "BTC",
            "quote_asset": "TMN",
            "is_spot": True,
            "is_active": True,
            "amount_precision": 6,
            "price_precision": 2,
        }
    ]
    universe = MarketUniverse.build(
        markets=raw_markets,
        local_denylist=["DUMMY/TMN"],
        package_unavailable=[],
    )
    assert universe.get_precision("BTCTMN") == (6, 2)
    assert universe.get_precision("UNKNOWN") is None


def test_from_actual_local_denylist_file():
    denylist_file = Path("docs/sources/inactive_markets.json")
    assert denylist_file.exists()

    raw_markets = [
        {"symbol": "BTCTMN", "is_spot": True, "is_active": True, "amount_precision": 8, "price_precision": 0},
        {"symbol": "ATMN", "is_spot": True, "is_active": True, "amount_precision": 2, "price_precision": 0},
    ]
    package_unavailable = ["IPTMN"]

    universe = MarketUniverse.from_files(
        markets_data=raw_markets,
        local_denylist_path=denylist_file,
        package_data={"result": {"unavailableMarkets": package_unavailable}},
    )

    # ATMN is in docs/sources/inactive_markets.json as "A/TMN"
    assert universe.is_allowed("ATMN") is False
    # BTCTMN is not denylisted
    assert universe.is_allowed("BTCTMN") is True

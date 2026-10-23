"""Tests for WallexMarketDataAdapter (Ticket 23)."""
import pytest
from unittest.mock import MagicMock
import httpx
from wallex_agent.market_data_adapter import (
    WallexMarketDataAdapter,
    MarketDataError,
    LiveMarketSnapshot,
)

SAMPLE_V1_MARKETS_PAYLOAD = {
    "result": {
        "symbols": {
            "USDTTMN": {
                "symbol": "USDTTMN",
                "baseAsset": "USDT",
                "baseAssetPrecision": 8,
                "quoteAsset": "TMN",
                "quotePrecision": 0,
                "stepSize": 2,
                "tickSize": 0,
                "minQty": 0.01,
                "minNotional": 50000,
                "stats": {
                    "bidPrice": "272862.0000000000000000",
                    "askPrice": "272930.0000000000000000",
                    "lastPrice": "272861.0000000000000000",
                    "24h_volume": "704660.86",
                    "24h_ch": 0.84,
                },
            },
            "BTCTMN": {
                "symbol": "BTCTMN",
                "baseAsset": "BTC",
                "baseAssetPrecision": 8,
                "quoteAsset": "TMN",
                "quotePrecision": 0,
                "stepSize": 6,
                "tickSize": 0,
                "minQty": 0.00001,
                "minNotional": 100000,
                "stats": {
                    "bidPrice": "22220000000.0",
                    "askPrice": "22230000000.0",
                    "lastPrice": "22224100443.0",
                    "24h_volume": "3.5",
                    "24h_ch": 0.44,
                },
            },
        }
    },
    "success": True,
}


def test_adapter_parses_v1_markets_response():
    mock_client = MagicMock()
    mock_client.get.return_value = MagicMock(status_code=200, json=lambda: SAMPLE_V1_MARKETS_PAYLOAD)

    adapter = WallexMarketDataAdapter(http_client=mock_client)
    snapshots = adapter.refresh_all_markets()

    assert "USDTTMN" in snapshots
    assert "BTCTMN" in snapshots

    usdt = snapshots["USDTTMN"]
    assert usdt["symbol"] == "USDTTMN"
    assert usdt["base_asset"] == "USDT"
    assert usdt["quote_asset"] == "TMN"
    assert usdt["last_price"] == 272861.0
    assert usdt["bid_price"] == 272862.0
    assert usdt["ask_price"] == 272930.0
    assert usdt["min_notional"] == 50000.0
    assert usdt["is_stale"] is False
    assert usdt["spread_bps"] > 0


def test_adapter_get_usdttmn_rate():
    mock_client = MagicMock()
    mock_client.get.return_value = MagicMock(status_code=200, json=lambda: SAMPLE_V1_MARKETS_PAYLOAD)

    adapter = WallexMarketDataAdapter(http_client=mock_client)
    rate = adapter.get_usdttmn_rate()
    assert rate == 272861.0
    assert rate != 70000.0  # Must never return stale 70,000 default


def test_adapter_fails_closed_on_network_error_without_hardcoded_prices():
    mock_client = MagicMock()
    mock_client.get.side_effect = httpx.ConnectError("Network unreachable")

    adapter = WallexMarketDataAdapter(http_client=mock_client)
    with pytest.raises(MarketDataError):
        adapter.refresh_all_markets()


def test_adapter_rejects_corrupted_or_non_finite_prices():
    corrupted_payload = {
        "result": {
            "symbols": {
                "CORRUPT": {
                    "symbol": "CORRUPT",
                    "baseAsset": "X",
                    "quoteAsset": "TMN",
                    "stats": {
                        "bidPrice": "-10.0",
                        "askPrice": "NaN",
                        "lastPrice": "0.0",
                    },
                }
            }
        },
        "success": True,
    }
    mock_client = MagicMock()
    mock_client.get.return_value = MagicMock(status_code=200, json=lambda: corrupted_payload)

    adapter = WallexMarketDataAdapter(http_client=mock_client)
    snapshots = adapter.refresh_all_markets()
    assert "CORRUPT" not in snapshots

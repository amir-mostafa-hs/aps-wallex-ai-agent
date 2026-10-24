import pytest
from unittest.mock import MagicMock
import httpx
from wallex_agent.wallex_client import WallexExchangeClient


def test_wallex_client_headers_without_subaccount():
    client = WallexExchangeClient(api_key="my-key", base_url="https://api.wallex.ir")
    headers = client._get_headers()
    assert headers["X-API-Key"] == "my-key"
    assert "sub-account-client-id" not in headers


def test_wallex_client_headers_with_subaccount():
    client = WallexExchangeClient(api_key="my-key", sub_account_client_id="sub-123", base_url="https://api.wallex.ir")
    headers = client._get_headers()
    assert headers["X-API-Key"] == "my-key"
    assert headers["sub-account-client-id"] == "sub-123"


def test_wallex_client_create_order_success():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "result": {
            "id": 12345,
            "clientId": "test-cid",
            "status": "SUBMITTED",
            "executedQty": "0",
            "executedSum": "0",
            "fee": "0",
        },
    }
    mock_http.post.return_value = mock_resp

    client = WallexExchangeClient(api_key="test-key", http_client=mock_http)
    res = client.create_order(
        symbol="BTCTMN",
        side="BUY",
        order_type="LIMIT",
        price=100000000.0,
        quantity=0.001,
        client_id="test-cid",
    )

    assert res["success"] is True
    assert res["result"]["id"] == 12345
    mock_http.post.assert_called_once()
    args, kwargs = mock_http.post.call_args
    assert args[0] == "https://api.wallex.ir/v1/account/orders"
    assert kwargs["json"]["client_id"] == "test-cid"
    assert kwargs["json"]["symbol"] == "BTCTMN"
    assert kwargs["json"]["side"] == "BUY"


def test_wallex_client_get_order():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "result": {
            "id": 12345,
            "clientId": "test-cid",
            "status": "FILLED",
            "executedQty": "0.001",
            "executedSum": "100000",
            "fee": "250",
        },
    }
    mock_http.get.return_value = mock_resp

    client = WallexExchangeClient(api_key="test-key", http_client=mock_http)
    res = client.get_order("test-cid")
    assert res["success"] is True
    assert res["result"]["status"] == "FILLED"
    mock_http.get.assert_called_once_with(
        "https://api.wallex.ir/v1/account/orders/test-cid",
        headers=client._get_headers(),
    )


def test_wallex_client_cancel_order():
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "result": {"status": "CANCELLED"}}
    mock_http.delete.return_value = mock_resp

    client = WallexExchangeClient(api_key="test-key", http_client=mock_http)
    res = client.cancel_order("test-cid")
    assert res["success"] is True
    mock_http.delete.assert_called_once_with(
        "https://api.wallex.ir/v1/account/orders/test-cid",
        headers=client._get_headers(),
    )


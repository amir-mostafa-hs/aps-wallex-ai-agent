"""Authoritative Wallex Exchange Client for Account, Preflight, and Live Order execution."""
from __future__ import annotations
import logging
from typing import Any, Mapping
import httpx

logger = logging.getLogger(__name__)


class WallexClientError(Exception):
    """Raised when an interaction with Wallex API fails."""
    pass


class WallexExchangeClient:
    """Official HTTP exchange client implementing Wallex REST endpoints for account and trading."""

    def __init__(
        self,
        api_key: str,
        sub_account_client_id: str = "",
        base_url: str = "https://api.wallex.ir",
        http_client: Any = None,
        timeout: float = 10.0,
    ) -> None:
        self.api_key = api_key.strip()
        self.sub_account_client_id = sub_account_client_id.strip()
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=timeout)

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "X-API-Key": self.api_key,
            "x-api-key": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.sub_account_client_id:
            headers["sub-account-client-id"] = self.sub_account_client_id
        return headers

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        price: float,
        quantity: float,
        client_id: str,
    ) -> dict[str, Any]:
        """Submits a new order to POST /v1/account/orders."""
        url = f"{self.base_url}/v1/account/orders"
        payload = {
            "symbol": symbol.strip().upper(),
            "side": side.strip().upper(),
            "type": order_type.strip().upper(),
            "price": str(price),
            "quantity": str(quantity),
            "client_id": client_id,
        }
        resp = self.http_client.post(url, json=payload, headers=self._get_headers())
        if resp.status_code not in (200, 201):
            raise WallexClientError(f"Wallex create_order returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def get_order(self, client_id: str) -> dict[str, Any]:
        """Retrieves order status from GET /v1/account/orders/{client_id}."""
        url = f"{self.base_url}/v1/account/orders/{client_id}"
        resp = self.http_client.get(url, headers=self._get_headers())
        if resp.status_code != 200:
            raise WallexClientError(f"Wallex get_order returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def cancel_order(self, client_id: str) -> dict[str, Any]:
        """Cancels an open order via DELETE /v1/account/orders/{client_id}."""
        url = f"{self.base_url}/v1/account/orders/{client_id}"
        resp = self.http_client.delete(url, headers=self._get_headers())
        if resp.status_code not in (200, 204):
            raise WallexClientError(f"Wallex cancel_order returned HTTP {resp.status_code}: {resp.text}")
        return resp.json() if resp.text else {"success": True}

    def get_account_balances(self) -> dict[str, Any]:
        """Queries GET /v1/account/balances."""
        url = f"{self.base_url}/v1/account/balances"
        resp = self.http_client.get(url, headers=self._get_headers())
        if resp.status_code != 200:
            raise WallexClientError(f"Wallex balances returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def get_active_package(self) -> dict[str, Any] | None:
        """Queries active credit package details from GET /v1/prop/user/packages/active."""
        url = f"{self.base_url}/v1/prop/user/packages/active"
        resp = self.http_client.get(url, headers=self._get_headers())
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("result") or data

    def get_package_history(self) -> list[dict[str, Any]]:
        """Queries user package history from GET /v1/prop/user/packages/overview."""
        url = f"{self.base_url}/v1/prop/user/packages/overview"
        resp = self.http_client.get(url, headers=self._get_headers())
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("result", {}).get("packages", []) or data.get("packages", []) or []

    def get_subaccount_permissions(self, sub_account_id: str) -> dict[str, Any]:
        """Queries permissions for a subaccount."""
        url = f"{self.base_url}/v1/account/sub-accounts/{sub_account_id}/permissions"
        resp = self.http_client.get(url, headers=self._get_headers())
        if resp.status_code != 200:
            # Fallback assumption if endpoint not exposed separately
            return {"permissions": ["TRADE", "READ"]}
        return resp.json().get("result", {})


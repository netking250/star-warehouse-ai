"""Production HTTP adapter for ERP/OMS/payment/logistics gateways."""

from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.adapters.contracts import (
    AccountDTO,
    AdapterContext,
    CartDTO,
    CartItemDTO,
    InventoryDTO,
    InvoiceDTO,
    LogisticsDTO,
    NotificationCommand,
    OrderDTO,
    PaymentDTO,
    ProductDTO,
    ProductQuery,
    RefundDTO,
)
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.resilience import ResilientExecutor
from app.core.config import settings

TModel = TypeVar("TModel", bound=BaseModel)


class ProductionBusinessHTTPAdapter:
    """HTTP implementation shared by all production business ports."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        client: httpx.AsyncClient | None = None,
        executor: ResilientExecutor | None = None,
    ) -> None:
        if not base_url.startswith("https://") and not settings.BUSINESS_API_ALLOW_INSECURE_HTTP:
            raise ValueError("Production business API must use HTTPS")
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._client = client
        self._executor = executor or ResilientExecutor(
            timeout_seconds=settings.BUSINESS_API_TIMEOUT_SECONDS,
            max_retries=settings.BUSINESS_API_MAX_RETRIES,
            failure_threshold=settings.BUSINESS_API_CIRCUIT_FAILURE_THRESHOLD,
            recovery_seconds=settings.BUSINESS_API_CIRCUIT_RECOVERY_SECONDS,
        )

    async def _request(
        self,
        method: str,
        path: str,
        context: AdapterContext,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        async def call() -> Any:
            client = self._client or httpx.AsyncClient()
            owns_client = self._client is None
            try:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    params=params,
                    json=json_body,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "X-Tenant-ID": context.tenant_id,
                        "X-User-ID": str(context.user_id),
                        "X-Correlation-ID": context.correlation_id,
                    },
                )
                if response.status_code == 404:
                    return None
                if response.status_code == 429:
                    raise AdapterError(
                        AdapterErrorCode.RATE_LIMITED,
                        "Upstream rate limit exceeded",
                        service="business_api",
                        retryable=True,
                    )
                if response.status_code >= 500:
                    raise AdapterError(
                        AdapterErrorCode.UPSTREAM_ERROR,
                        "Upstream service failed",
                        service="business_api",
                        retryable=True,
                    )
                if response.status_code in {401, 403}:
                    raise AdapterError(
                        AdapterErrorCode.UNAUTHORIZED
                        if response.status_code == 401
                        else AdapterErrorCode.FORBIDDEN,
                        "Upstream authorization failed",
                        service="business_api",
                    )
                if response.status_code == 409:
                    raise AdapterError(
                        AdapterErrorCode.CONFLICT,
                        "Upstream resource conflict",
                        service="business_api",
                    )
                if response.status_code in {400, 422}:
                    raise AdapterError(
                        AdapterErrorCode.VALIDATION,
                        "Upstream request validation failed",
                        service="business_api",
                    )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as error:
                raise AdapterError(
                    AdapterErrorCode.TIMEOUT,
                    "Upstream request timed out",
                    service="business_api",
                    retryable=True,
                ) from error
            except httpx.HTTPError as error:
                raise AdapterError(
                    AdapterErrorCode.UNAVAILABLE,
                    "Upstream service is unavailable",
                    service="business_api",
                    retryable=True,
                ) from error
            finally:
                if owns_client:
                    await client.aclose()

        return await self._executor.run("business_api", f"{method} {path}", call)

    async def get_account(self, context: AdapterContext) -> AccountDTO | None:
        data = await self._request("GET", "/identity/me", context)
        return AccountDTO.model_validate(data) if data else None

    async def search(self, query: ProductQuery, context: AdapterContext) -> list[ProductDTO]:
        data = await self._request(
            "GET",
            "/products",
            context,
            params=query.model_dump(
                exclude_none=True,
                exclude={"conversation_history"},
                mode="json",
            ),
        )
        return [ProductDTO.model_validate(item) for item in data or []]

    async def get_inventory(self, sku: str, context: AdapterContext) -> InventoryDTO | None:
        data = await self._request("GET", f"/inventory/{quote(sku, safe='')}", context)
        return InventoryDTO.model_validate(data) if data else None

    async def get_order(self, order_sn: str | None, context: AdapterContext) -> OrderDTO | None:
        path = f"/orders/{quote(order_sn, safe='')}" if order_sn else "/orders/latest"
        data = await self._request("GET", path, context)
        return OrderDTO.model_validate(data) if data else None

    async def get_payment(self, order_sn: str, context: AdapterContext) -> PaymentDTO | None:
        data = await self._request("GET", f"/payments/{quote(order_sn, safe='')}", context)
        return PaymentDTO.model_validate(data) if data else None

    async def get_invoice(self, order_sn: str, context: AdapterContext) -> InvoiceDTO | None:
        data = await self._request("GET", f"/invoices/{quote(order_sn, safe='')}", context)
        return InvoiceDTO.model_validate(data) if data else None

    async def get_tracking(self, order_sn: str, context: AdapterContext) -> LogisticsDTO | None:
        data = await self._request("GET", f"/logistics/{quote(order_sn, safe='')}", context)
        return LogisticsDTO.model_validate(data) if data else None

    async def get_cart(self, context: AdapterContext) -> CartDTO:
        data = await self._request("GET", "/cart", context)
        return CartDTO.model_validate(data or {"user_id": context.user_id})

    async def add_item(self, item: CartItemDTO, context: AdapterContext) -> CartDTO:
        data = await self._request(
            "POST", "/cart/items", context, json_body=item.model_dump(mode="json")
        )
        return CartDTO.model_validate(data)

    async def remove_item(self, item_key: str, context: AdapterContext) -> CartDTO:
        data = await self._request("DELETE", f"/cart/items/{quote(item_key, safe='')}", context)
        return CartDTO.model_validate(data)

    async def update_quantity(
        self, item_key: str, quantity: int, context: AdapterContext
    ) -> CartDTO:
        data = await self._request(
            "PATCH",
            f"/cart/items/{quote(item_key, safe='')}",
            context,
            json_body={"quantity": quantity},
        )
        return CartDTO.model_validate(data)

    async def list_refunds(
        self, order_id: int | str | None, context: AdapterContext
    ) -> list[RefundDTO]:
        data = await self._request("GET", "/refunds", context, params={"order_id": order_id})
        return [RefundDTO.model_validate(item) for item in data or []]

    async def send(self, command: NotificationCommand, context: AdapterContext) -> str:
        data = await self._request(
            "POST", "/notifications", context, json_body=command.model_dump(mode="json")
        )
        return str(data["message_id"])

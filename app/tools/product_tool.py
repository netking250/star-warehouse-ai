"""Product tool backed exclusively by the product port."""

from decimal import Decimal
from typing import Any

from qdrant_client import AsyncQdrantClient

from app.adapters.context import current_adapter_context
from app.adapters.contracts import ProductDTO, ProductQuery
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.local import QdrantProductAdapter
from app.adapters.ports import ProductPort
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class ProductTool(BaseTool):
    name = "product"
    description = "搜索商品目录并回答商品相关问题"

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient | None = None,
        rewriter: Any | None = None,
        embedder: Any | None = None,
        collection_name: str | None = None,
        product_port: ProductPort | None = None,
    ) -> None:
        local = QdrantProductAdapter(
            client=qdrant_client,
            rewriter=rewriter,
            embedder=embedder,
            collection_name=collection_name,
        )
        self._product = product_port or local
        self.collection_name = local.collection_name

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        """Search tenant-owned products through the configured adapter."""
        slots = state.get("slots") or {}
        user_id = state.get("user_id")
        if user_id is None:
            return ToolResult(output={"status": "error", "reason": "无法识别用户身份"})
        query_text = str(
            slots.get("product_query") or slots.get("query") or state.get("question", "")
        )
        query = ProductQuery(
            query=query_text,
            category=slots.get("category") or kwargs.get("category"),
            min_price=self._decimal(slots.get("min_price") or kwargs.get("min_price")),
            max_price=self._decimal(slots.get("max_price") or kwargs.get("max_price")),
            in_stock=slots.get("in_stock")
            if slots.get("in_stock") is not None
            else kwargs.get("in_stock"),
            conversation_history=list(state.get("history") or []),
        )
        try:
            products = await self._product.search(query, current_adapter_context(user_id))
        except AdapterError as error:
            return ToolResult(
                output={
                    "status": "not_found" if error.code == AdapterErrorCode.NOT_FOUND else "error",
                    "reason": str(error)
                    if error.code == AdapterErrorCode.NOT_FOUND
                    else "商品服务暂时不可用，请稍后重试",
                }
            )
        payloads = [self._output(product) for product in products]
        return ToolResult(
            output={
                "status": "success" if payloads else "not_found",
                "products": payloads,
                "direct_answer": self._try_direct_answer(query_text, payloads),
                "query": query_text,
            }
        )

    @staticmethod
    def _decimal(value: object) -> Decimal | None:
        return Decimal(str(value)) if value is not None else None

    @staticmethod
    def _output(product: ProductDTO) -> dict[str, Any]:
        data = product.model_dump(mode="json")
        data["id"] = data.pop("product_id")
        if product.price is not None:
            data["price"] = float(product.price)
        return data

    @staticmethod
    def _try_direct_answer(query: str, products: list[dict]) -> str | None:
        if not products:
            return None
        top = products[0]
        attrs = top.get("attributes") or {}
        attribute_keywords = {
            "屏幕": "屏幕",
            "刷新率": "刷新率",
            "hz": "刷新率",
            "电池": "电池",
            "相机": "相机",
            "重量": "重量",
            "尺寸": "尺寸",
            "内存": "内存",
            "存储": "存储",
            "颜色": "颜色",
            "材质": "材质",
        }
        for keyword, attribute in attribute_keywords.items():
            if keyword in query.lower() and attribute in attrs:
                return f"{top['name']} 的{keyword}为 {attrs[attribute]}。"
        return None

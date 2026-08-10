"""Initialize tenant-scoped Qdrant collections and seed bundled demo data."""

import asyncio

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.core.tenancy import get_current_tenant_id, namespaced_collection
from scripts.etl_qdrant import main as seed_knowledge
from scripts.seed_product_catalog import main as seed_products


async def _tenant_data_exists(
    client: AsyncQdrantClient,
    collection_name: str,
) -> bool:
    """Return whether a collection contains data for the active tenant."""
    if not await client.collection_exists(collection_name):
        return False
    result = await client.count(
        collection_name=collection_name,
        count_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=get_current_tenant_id()),
                )
            ]
        ),
        exact=True,
    )
    return result.count > 0


async def main() -> None:
    """Seed missing knowledge and product data without recreating collections."""
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
        timeout=settings.QDRANT_TIMEOUT,
    )
    try:
        knowledge_exists, products_exist = await asyncio.gather(
            _tenant_data_exists(
                client,
                namespaced_collection(settings.QDRANT_COLLECTION_NAME),
            ),
            _tenant_data_exists(client, namespaced_collection("product_catalog")),
        )
    finally:
        await client.close()

    if not knowledge_exists:
        await seed_knowledge(base_dir="data", recreate=False)
    if not products_exist:
        await seed_products()

    if knowledge_exists and products_exist:
        print("Vector data is already initialized for the active tenant.")


if __name__ == "__main__":
    asyncio.run(main())

import uuid

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, Modifier, SparseVectorParams, VectorParams

from app.core.config import settings
from app.core.tenancy import namespaced_collection
from app.retrieval.tenant_boundary import (
    active_vector_tenant,
    tenant_filter,
    tenant_filter_selector,
    tenant_payload,
)


class QdrantKnowledgeClient:
    def __init__(
        self,
        url: str,
        *,
        collection_name: str,
        api_key: str | None,
        client: AsyncQdrantClient | None = None,
    ):
        self.collection_name = namespaced_collection(collection_name)
        if client is not None:
            self.client = client
        elif url == ":memory:":
            self.client = AsyncQdrantClient(location=":memory:", timeout=settings.QDRANT_TIMEOUT)
        else:
            self.client = AsyncQdrantClient(
                url=url, api_key=api_key, timeout=settings.QDRANT_TIMEOUT
            )

    async def aclose(self) -> None:
        await self.client.close()

    async def ensure_collection(self) -> None:
        exists = await self.client.collection_exists(self.collection_name)
        if exists:
            return

        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)
            },
            sparse_vectors_config={"sparse": SparseVectorParams(modifier=Modifier.IDF)},
        )

    async def recreate_collection(self) -> None:
        try:
            await self.client.delete_collection(self.collection_name)
        except UnexpectedResponse as exc:
            if exc.status_code != 404:
                raise
        await self.ensure_collection()

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        tenant_id = active_vector_tenant()
        scoped_points = [
            point.model_copy(
                update={
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{tenant_id}:{point.id}")),
                    "payload": tenant_payload(point.payload or {}),
                }
            )
            for point in points
        ]
        await self.client.upsert(collection_name=self.collection_name, points=scoped_points)

    async def delete_document(self, document_id: int) -> bool:
        """Delete only the active tenant's chunks for a knowledge document."""
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=tenant_filter_selector(
                models.FieldCondition(key="doc_id", match=models.MatchValue(value=document_id))
            ),
            wait=True,
        )
        return True

    async def query_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        dense_limit: int = 15,
        sparse_limit: int = 15,
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=dense_limit,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    limit=sparse_limit,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=settings.RETRIEVER_RRF_K)),
            query_filter=tenant_filter(),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    async def query_dense(
        self,
        dense_vector: list[float],
        limit: int = 15,
    ) -> list[models.ScoredPoint]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=dense_vector,
            using="dense",
            query_filter=tenant_filter(),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

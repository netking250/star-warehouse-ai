"""Knowledge source-object and derived-vector lifecycle orchestration."""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.storage.knowledge import KnowledgeObjectStore, get_knowledge_object_store


class KnowledgeVectorStore(Protocol):
    """Required derived-vector operations for knowledge deletion."""

    async def ensure_collection(self) -> None:
        """Ensure the tenant-scoped collection exists."""
        ...

    async def delete_document(self, document_id: int) -> bool:
        """Delete one tenant's derived points for a document."""
        ...

    async def aclose(self) -> None:
        """Close resources owned by the vector adapter."""
        ...


async def delete_knowledge_assets(
    *,
    tenant_id: str,
    document_id: int,
    object_key: str,
    object_store: KnowledgeObjectStore | None = None,
    vector_store: KnowledgeVectorStore | None = None,
) -> None:
    """Delete source bytes and tenant-scoped derived vectors for one document."""
    source_store = object_store or get_knowledge_object_store()
    vectors = vector_store or QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY.get_secret_value(),
    )
    owns_vectors = vector_store is None
    try:
        await vectors.ensure_collection()
        await vectors.delete_document(document_id)
        await source_store.delete(tenant_id=tenant_id, object_key=object_key)
    finally:
        if owns_vectors:
            await vectors.aclose()

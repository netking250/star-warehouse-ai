import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from sqlalchemy.exc import SQLAlchemyError

from app.context.pii_filter import log_pii_detection, pii_filter
from app.core.cache import CacheManager
from app.core.config import settings
from app.core.tenancy import namespaced_collection
from app.memory.consistency import MemoryVectorDocument, VectorIndexUnavailableError
from app.retrieval.embeddings import create_embedding_model
from app.retrieval.tenant_boundary import (
    active_vector_tenant,
    tenant_filter,
    tenant_filter_selector,
    tenant_payload,
)

logger = logging.getLogger(__name__)
_SUMMARY_POINT_NAMESPACE = uuid.UUID("9c47969d-3f15-48ee-a488-9b404b445936")


def _summary_point_id(*, tenant_id: str, memory_id: int) -> str:
    """Return the stable Qdrant point identity for one structured summary."""
    return str(uuid.uuid5(_SUMMARY_POINT_NAMESPACE, f"{tenant_id}:interaction_summary:{memory_id}"))


class VectorMemoryManager:
    """Manages conversation memory vectors in Qdrant's `conversation_memory` collection."""

    COLLECTION_NAME = namespaced_collection("conversation_memory")

    def __init__(self, client=None, embedder=None, cache_manager: CacheManager | None = None):
        if client is None:
            if settings.QDRANT_URL == ":memory:":
                self.client = AsyncQdrantClient(
                    location=":memory:", timeout=settings.QDRANT_TIMEOUT
                )
            else:
                self.client = AsyncQdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY.get_secret_value(),
                    timeout=settings.QDRANT_TIMEOUT,
                )
        else:
            self.client = client
        self._embedder = embedder if embedder is not None else create_embedding_model()
        self._collection_ensured: bool = False
        self._cache = cache_manager

    async def aclose(self) -> None:
        await self.client.close()

    async def ensure_collection(self) -> None:
        if self._collection_ensured:
            return
        exists = await self.client.collection_exists(self.COLLECTION_NAME)
        if exists:
            self._collection_ensured = True
            return

        await self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config={
                "dense": VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)
            },
        )
        try:
            await self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
        except (SQLAlchemyError, RuntimeError, OSError):
            logger.exception("Failed to create payload index for user_id")
        self._collection_ensured = True

    async def upsert_message(
        self,
        user_id: int,
        thread_id: str,
        message_role: str,
        content: str,
        timestamp: str,
        intent: str | None = None,
    ) -> None:
        """Write compatibility conversation history outside structured memory.

        New structured-memory callers must use ``upsert_summary`` through the
        transactional outbox projection path.
        """
        await self.ensure_collection()

        pii_result = pii_filter.filter_text(content)
        filtered_content = pii_result.redacted_text
        if pii_result.has_pii:
            log_pii_detection(
                user_id=user_id,
                thread_id=thread_id,
                source="vector_memory",
                detections=pii_result.detections,
            )

        embeddings = await self._embedder.aembed_documents([filtered_content])
        vector = embeddings[0]

        point_id = str(uuid.uuid4())
        payload: dict[str, object] = tenant_payload(
            {
                "user_id": user_id,
                "thread_id": thread_id,
                "message_role": message_role,
                "content": filtered_content,
                "timestamp": timestamp,
            }
        )
        if intent is not None:
            payload["intent"] = intent

        await self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector={"dense": vector},
                    payload=payload,
                )
            ],
        )

    async def upsert_summary(self, document: MemoryVectorDocument) -> None:
        """Idempotently project an authoritative summary using a stable point ID."""
        active_vector_tenant(document.tenant_id)
        try:
            await self.ensure_collection()
            pii_result = pii_filter.filter_text(document.summary_text)
            filtered_content = pii_result.redacted_text
            if pii_result.has_pii:
                log_pii_detection(
                    user_id=document.user_id,
                    thread_id=document.thread_id,
                    source="structured_memory_vector",
                    detections=pii_result.detections,
                )
            embeddings = await self._embedder.aembed_documents([filtered_content])
            await self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=_summary_point_id(
                            tenant_id=document.tenant_id,
                            memory_id=document.memory_id,
                        ),
                        vector={"dense": embeddings[0]},
                        payload=tenant_payload(
                            {
                                "memory_id": document.memory_id,
                                "memory_version": document.version,
                                "user_id": document.user_id,
                                "thread_id": document.thread_id,
                                "message_role": "summary",
                                "content": filtered_content,
                                "timestamp": document.updated_at,
                                "intent": document.resolved_intent,
                            },
                            tenant_id=document.tenant_id,
                        ),
                    )
                ],
            )
        except (UnexpectedResponse, ConnectionError, TimeoutError, OSError, RuntimeError) as error:
            raise VectorIndexUnavailableError(type(error).__name__) from error

    async def delete_summary(self, *, tenant_id: str, memory_id: int) -> None:
        """Idempotently remove one derived summary point."""
        active_vector_tenant(tenant_id)
        try:
            if not await self.client.collection_exists(self.COLLECTION_NAME):
                return
            await self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=tenant_filter_selector(
                    models.FieldCondition(
                        key="memory_id", match=models.MatchValue(value=memory_id)
                    ),
                    tenant_id=tenant_id,
                ),
            )
        except (UnexpectedResponse, ConnectionError, TimeoutError, OSError, RuntimeError) as error:
            raise VectorIndexUnavailableError(type(error).__name__) from error

    async def get_summary_version(self, *, tenant_id: str, memory_id: int) -> int | None:
        """Read the indexed version used by the reconciliation command."""
        active_vector_tenant(tenant_id)
        try:
            if not await self.client.collection_exists(self.COLLECTION_NAME):
                return None
            points = await self.client.retrieve(
                collection_name=self.COLLECTION_NAME,
                ids=[_summary_point_id(tenant_id=tenant_id, memory_id=memory_id)],
                with_payload=True,
                with_vectors=False,
            )
        except (UnexpectedResponse, ConnectionError, TimeoutError, OSError, RuntimeError) as error:
            raise VectorIndexUnavailableError(type(error).__name__) from error
        if not points or points[0].payload is None:
            return None
        if points[0].payload.get("tenant_id") != tenant_id:
            return None
        version = points[0].payload.get("memory_version")
        return version if isinstance(version, int) else None

    async def search_similar(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
        message_role: str | None = None,
    ) -> list[dict]:
        await self.ensure_collection()

        query_hash = hashlib.sha256(query_text.encode()).hexdigest()[:16]
        if self._cache is not None:
            cached = await self._cache.get_vector_search(
                user_id, query_hash, top_k, message_role=message_role
            )
            if cached is not None:
                return cached

        embeddings = await self._embedder.aembed_documents([query_text])
        query_vector = embeddings[0]

        must_conditions: list[models.Condition] = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id),
            ),
        ]
        if message_role is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="message_role",
                    match=models.MatchValue(value=message_role),
                )
            )

        response = await self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            using="dense",
            query_filter=tenant_filter(*must_conditions),
            limit=top_k,
            with_payload=True,
        )

        results = [
            {**point.payload, "score": point.score}
            for point in response.points
            if point.payload is not None
        ]

        if self._cache is not None:
            await self._cache.set_vector_search(
                user_id, query_hash, top_k, results, message_role=message_role, ttl=300
            )

        return results

    async def prune_old_messages(self, retention_days: int) -> None:
        exists = await self.client.collection_exists(self.COLLECTION_NAME)
        if not exists:
            return

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff.isoformat()

        total_pruned = 0
        offset = None

        while True:
            try:
                batch, offset = await self.client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    scroll_filter=tenant_filter(),
                )
            except UnexpectedResponse as exc:
                if exc.status_code == 404:
                    return
                raise

            if not batch:
                break

            batch_ids: list[str | int | uuid.UUID] = []
            for point in batch:
                ts = point.payload.get("timestamp") if point.payload else None
                if isinstance(ts, str) and ts < cutoff_iso:
                    batch_ids.append(str(point.id))

            if batch_ids:
                await self.client.delete(
                    collection_name=self.COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=batch_ids),
                )
                total_pruned += len(batch_ids)

            if offset is None:
                break

        if total_pruned:
            logger.info(
                "Pruned %d old messages from %s",
                total_pruned,
                self.COLLECTION_NAME,
            )

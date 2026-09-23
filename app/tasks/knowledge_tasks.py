"""Tenant-scoped knowledge ingestion tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import models
from sqlmodel import select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_maker
from app.core.redis import create_redis_client
from app.core.tenancy import get_current_tenant_id, namespaced_key
from app.core.utils import utc_now
from app.models.knowledge_document import KnowledgeDocument
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model
from app.retrieval.sparse_embedder import SparseTextEmbedder
from app.storage.knowledge import get_knowledge_object_store
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.envelope import TaskEnvelope

logger = logging.getLogger(__name__)
BATCH_SIZE = 32


class InvalidDenseEmbeddingError(RuntimeError):
    """Raised when a provider degradation returns a non-searchable dense vector."""


class KnowledgeSyncPayload(BaseModel):
    """Identifier required for a tenant-scoped knowledge sync."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: int = Field(gt=0)


def _invalidate_retrieval_cache() -> None:
    """Invalidate all retrieval caches after a knowledge-base update."""
    try:
        client = create_redis_client()

        async def _do_invalidate() -> None:
            keys: list[str] = []
            async for key in client.scan_iter(match=namespaced_key("retrieval:*")):
                keys.append(key)
            if keys:
                await client.delete(*keys)
            await client.aclose()

        asyncio.run(_do_invalidate())
        logger.info("Invalidated retrieval cache after knowledge sync")
    except Exception as exc:
        logger.warning("Failed to invalidate retrieval cache: %s", exc)


def load_documents(file_path: str) -> list[Document]:
    """Load a local file for backward-compatible direct-loader callers."""
    path = Path(file_path)
    return load_documents_from_bytes(path.read_bytes(), path.name)


def load_documents_from_bytes(content: bytes, source_name: str) -> list[Document]:
    """Parse source bytes without making a durable task depend on a local path."""
    extension = os.path.splitext(source_name)[1].lower()
    if extension in {".md", ".txt"}:
        return [
            Document(
                page_content=content.decode("utf-8"),
                metadata={"source": source_name},
            )
        ]
    if extension == ".pdf":
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
                temporary.write(content)
                temporary_path = Path(temporary.name)
            documents = PyPDFLoader(str(temporary_path)).load()
            for document in documents:
                document.metadata["source"] = source_name
            return documents
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    if extension == ".json":
        data = json.loads(content.decode("utf-8"))
        text = json.dumps(data, ensure_ascii=False)
        return [Document(page_content=text, metadata={"source": source_name})]
    raise ValueError(f"Unsupported file type: {extension}")


async def _embed_dense(texts: list[str]) -> list[list[float]]:
    return await create_embedding_model().aembed_documents(texts)


async def _embed_sparse(
    sparse_embedder: SparseTextEmbedder, texts: list[str]
) -> list[models.SparseVector]:
    return await sparse_embedder.aembed(texts)


async def ingest_knowledge_document(
    document_id: int, object_key: str, source_name: str
) -> dict[str, Any]:
    """Resolve source bytes through storage and rebuild the derived vector set."""
    object_store = get_knowledge_object_store()
    source_bytes = await object_store.read_bytes(
        tenant_id=get_current_tenant_id(), object_key=object_key
    )
    documents = await asyncio.to_thread(load_documents_from_bytes, source_bytes, source_name)

    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY.get_secret_value(),
    )
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )
        split_documents = text_splitter.split_documents(documents)
        total_chunks = len(split_documents)
        if total_chunks == 0:
            await qdrant_client.ensure_collection()
            await qdrant_client.delete_document(document_id)
            return {"status": "success", "chunks": 0, "message": "No content found"}

        sparse_embedder = SparseTextEmbedder()
        points: list[models.PointStruct] = []
        for offset in range(0, total_chunks, BATCH_SIZE):
            batch_documents = split_documents[offset : offset + BATCH_SIZE]
            batch_texts: list[str] = []
            batch_metadata: list[dict[str, Any]] = []
            for index, document in enumerate(batch_documents):
                cleaned = document.page_content.strip()
                if cleaned:
                    batch_texts.append(cleaned)
                    page = int(document.metadata.get("page", 0)) + 1
                    batch_metadata.append({"page": page, "chunk_index": offset + index})

            if not batch_texts:
                continue

            dense_vectors, sparse_vectors = await asyncio.gather(
                _embed_dense(batch_texts),
                _embed_sparse(sparse_embedder, batch_texts),
            )
            if any(
                not vector or not any(value != 0.0 for value in vector) for vector in dense_vectors
            ):
                raise InvalidDenseEmbeddingError(
                    "Embedding provider returned an unusable all-zero dense vector"
                )
            for index, text in enumerate(batch_texts):
                points.append(
                    models.PointStruct(
                        id=f"{document_id}_{offset + index}",
                        vector={
                            "dense": dense_vectors[index],
                            "sparse": sparse_vectors[index],
                        },
                        payload={
                            "content": text,
                            "source": source_name,
                            "doc_id": document_id,
                            "meta_data": batch_metadata[index],
                        },
                    )
                )

        await qdrant_client.ensure_collection()
        await qdrant_client.delete_document(document_id)
        for offset in range(0, len(points), BATCH_SIZE):
            await qdrant_client.upsert_chunks(points[offset : offset + BATCH_SIZE])
        return {"status": "success", "chunks": len(points)}
    finally:
        await qdrant_client.aclose()


@celery_app.task(bind=True, name="knowledge.sync_document", max_retries=3, default_retry_delay=60)
def sync_knowledge_document(self, envelope: dict[str, object]) -> dict[str, Any]:
    """Synchronize one tenant-owned source object into the derived Qdrant index."""
    task_envelope = TaskEnvelope.from_message(envelope)
    payload = KnowledgeSyncPayload.model_validate(task_envelope.payload)
    document_id = payload.document_id
    with (
        task_execution_scope(
            task_envelope.task_context,
            task_name="celery.knowledge.sync_document",
            task_id=getattr(self.request, "id", None),
        ),
        sync_session_maker() as session,
    ):
        result = session.exec(select(KnowledgeDocument).where(KnowledgeDocument.id == document_id))
        document = result.one_or_none()
        if document is None:
            logger.error("Knowledge document %s not found", document_id)
            raise ValueError(f"Knowledge document {document_id} not found")

        document.sync_status = "running"
        document.sync_message = None
        session.add(document)
        session.commit()

        try:
            sync_result = asyncio.run(
                ingest_knowledge_document(
                    document_id,
                    document.storage_path,
                    document.filename,
                )
            )
            _invalidate_retrieval_cache()
            document.sync_status = "done"
            document.sync_message = "Synced successfully"
            document.last_synced_at = utc_now()
            document.updated_at = utc_now()
            session.add(document)
            session.commit()
            return {
                "status": "success",
                "document_id": document_id,
                "chunks": sync_result["chunks"],
            }
        except Exception as exc:
            logger.exception("Failed to sync knowledge document %s", document_id)
            final_attempt = self.request.retries >= int(self.max_retries or 0)
            document.sync_status = "failed" if final_attempt else "pending"
            document.sync_message = (
                "同步失败，已达到最大重试次数" if final_attempt else "同步失败，将自动重试"
            )
            document.updated_at = utc_now()
            session.add(document)
            session.commit()
            if final_attempt:
                return {
                    "status": "failed",
                    "document_id": document_id,
                    "message": "同步失败，已达到最大重试次数",
                }
            raise self.retry(exc=exc) from exc

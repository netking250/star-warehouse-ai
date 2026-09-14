import asyncio
import json
import logging
import os
from typing import Any

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, ConfigDict, Field
from qdrant_client import models
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_maker
from app.core.redis import create_redis_client
from app.core.tenancy import namespaced_key
from app.core.utils import utc_now
from app.models.knowledge_document import KnowledgeDocument
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model
from app.retrieval.sparse_embedder import SparseTextEmbedder
from app.task_runtime.binding import task_execution_scope
from app.task_runtime.envelope import TaskEnvelope


def _invalidate_retrieval_cache() -> None:
    """Invalidate all retrieval caches after knowledge base update."""
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


logger = logging.getLogger(__name__)
BATCH_SIZE = 32
UPLOAD_DIR = settings.KNOWLEDGE_UPLOAD_DIR


class KnowledgeSyncPayload(BaseModel):
    """Identifier required for a tenant-scoped knowledge sync."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: int = Field(gt=0)


def load_documents(file_path: str) -> list[Document]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".md", ".txt"]:
        return TextLoader(file_path, encoding="utf-8").load()
    elif ext == ".pdf":
        return PyPDFLoader(file_path).load()
    elif ext == ".json":
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
        text = json.dumps(data, ensure_ascii=False)
        return [Document(page_content=text, metadata={"source": file_path})]
    else:
        raise ValueError(f"Unsupported file type: {ext}")


async def _embed_dense(texts: list[str]) -> list[list[float]]:
    return await create_embedding_model().aembed_documents(texts)


async def _embed_sparse(
    sparse_embedder: SparseTextEmbedder, texts: list[str]
) -> list[models.SparseVector]:
    return await sparse_embedder.aembed(texts)


async def _do_sync(document_id: int, storage_path: str, source_name: str) -> dict[str, Any]:
    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY.get_secret_value(),
    )
    try:
        await qdrant_client.ensure_collection()
        await qdrant_client.delete_document(document_id)
        sparse_embedder = SparseTextEmbedder()

        docs = load_documents(storage_path)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
        )
        split_docs = text_splitter.split_documents(docs)
        total_chunks = len(split_docs)
        if total_chunks == 0:
            return {"status": "success", "chunks": 0, "message": "No content found"}

        points: list[models.PointStruct] = []
        for i in range(0, total_chunks, BATCH_SIZE):
            batch_docs = split_docs[i : i + BATCH_SIZE]
            batch_texts: list[str] = []
            batch_metas: list[dict] = []
            for idx, doc in enumerate(batch_docs):
                cleaned = doc.page_content.strip()
                if cleaned:
                    batch_texts.append(cleaned)
                    page = doc.metadata.get("page", 0) + 1
                    batch_metas.append({"page": page, "chunk_index": i + idx})

            if not batch_texts:
                continue

            dense_vectors, sparse_vectors = await asyncio.gather(
                _embed_dense(batch_texts),
                _embed_sparse(sparse_embedder, batch_texts),
            )

            for j, text in enumerate(batch_texts):
                point_id = f"{document_id}_{i + j}"
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector={
                            "dense": dense_vectors[j],
                            "sparse": sparse_vectors[j],
                        },
                        payload={
                            "content": text,
                            "source": source_name,
                            "doc_id": document_id,
                            "meta_data": batch_metas[j],
                        },
                    )
                )

        for i in range(0, len(points), BATCH_SIZE):
            await qdrant_client.upsert_chunks(points[i : i + BATCH_SIZE])

        return {"status": "success", "chunks": total_chunks}
    finally:
        await qdrant_client.aclose()


@celery_app.task(bind=True, name="knowledge.sync_document", max_retries=3, default_retry_delay=60)
def sync_knowledge_document(self, envelope: dict[str, object]) -> dict[str, Any]:
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
        doc = result.one_or_none()
        if not doc:
            logger.error("Knowledge document %s not found", document_id)
            raise ValueError(f"Knowledge document {document_id} not found")

        doc.sync_status = "running"
        doc.sync_message = None
        session.add(doc)
        session.commit()

        try:
            sync_result = asyncio.run(_do_sync(document_id, doc.storage_path, doc.filename))
            _invalidate_retrieval_cache()
            doc.sync_status = "done"
            doc.sync_message = "Synced successfully"
            doc.last_synced_at = utc_now()
            doc.updated_at = utc_now()
            session.add(doc)
            session.commit()
            return {
                "status": "success",
                "document_id": document_id,
                "chunks": sync_result["chunks"],
            }
        except (SQLAlchemyError, RuntimeError) as exc:
            logger.exception("Failed to sync knowledge document %s", document_id)
            doc.sync_status = "failed"
            doc.sync_message = "同步失败，已达到最大重试次数"
            doc.updated_at = utc_now()
            session.add(doc)
            session.commit()
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {
                    "status": "failed",
                    "document_id": document_id,
                    "message": "同步失败，已达到最大重试次数",
                }

import pytest
from qdrant_client import models

from app.core.tenancy import tenant_scope
from app.tasks.knowledge_tasks import ingest_knowledge_document


class _FakeStore:
    def __init__(self) -> None:
        self.reads: list[tuple[str, str]] = []

    async def read_bytes(self, *, tenant_id: str, object_key: str) -> bytes:
        self.reads.append((tenant_id, object_key))
        return b"STAR_WAREHOUSE_KB_WORKER_READ"


class _FakeQdrant:
    def __init__(self) -> None:
        self.deleted: list[int] = []
        self.points: list[models.PointStruct] = []

    async def ensure_collection(self) -> None:
        return None

    async def delete_document(self, document_id: int) -> bool:
        self.deleted.append(document_id)
        return True

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        self.points.extend(points)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_ingestion_resolves_object_key_through_canonical_store(monkeypatch):
    store = _FakeStore()
    qdrant = _FakeQdrant()
    monkeypatch.setattr("app.tasks.knowledge_tasks.get_knowledge_object_store", lambda: store)
    monkeypatch.setattr("app.tasks.knowledge_tasks.QdrantKnowledgeClient", lambda **_kwargs: qdrant)

    async def fake_dense(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]

    async def fake_sparse(_embedder, texts: list[str]) -> list[models.SparseVector]:
        return [models.SparseVector(indices=[0], values=[1.0]) for _ in texts]

    monkeypatch.setattr("app.tasks.knowledge_tasks._embed_dense", fake_dense)
    monkeypatch.setattr("app.tasks.knowledge_tasks._embed_sparse", fake_sparse)
    monkeypatch.setattr("app.tasks.knowledge_tasks.SparseTextEmbedder", lambda: object())

    with tenant_scope("default"):
        result = await ingest_knowledge_document(
            document_id=41,
            object_key="tenant/default/sentinel.txt",
            source_name="sentinel.txt",
        )

    assert result == {"status": "success", "chunks": 1}
    assert store.reads == [("default", "tenant/default/sentinel.txt")]
    assert qdrant.deleted == [41]
    assert len(qdrant.points) == 1
    payload = qdrant.points[0].payload
    assert payload is not None
    assert payload["content"] == "STAR_WAREHOUSE_KB_WORKER_READ"

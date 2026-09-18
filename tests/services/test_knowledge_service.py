import pytest

from app.services.knowledge_service import delete_knowledge_assets


class _FakeObjectStore:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    async def put_bytes(self, *, tenant_id: str, object_name: str, content: bytes) -> str:
        raise AssertionError("put_bytes is not expected during deletion")

    async def read_bytes(self, *, tenant_id: str, object_key: str) -> bytes:
        raise AssertionError("read_bytes is not expected during deletion")

    async def delete(self, *, tenant_id: str, object_key: str) -> bool:
        self.deleted.append((tenant_id, object_key))
        return True


class _FakeVectorStore:
    def __init__(self) -> None:
        self.ensured = False
        self.deleted: list[int] = []
        self.closed = False

    async def ensure_collection(self) -> None:
        self.ensured = True

    async def delete_document(self, document_id: int) -> bool:
        self.deleted.append(document_id)
        return True

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_delete_knowledge_assets_removes_source_and_derived_vectors() -> None:
    object_store = _FakeObjectStore()
    vector_store = _FakeVectorStore()

    await delete_knowledge_assets(
        tenant_id="tenant-a",
        document_id=17,
        object_key="tenant/tenant-a/source.txt",
        object_store=object_store,
        vector_store=vector_store,
    )

    assert vector_store.ensured is True
    assert vector_store.deleted == [17]
    assert object_store.deleted == [("tenant-a", "tenant/tenant-a/source.txt")]
    assert vector_store.closed is False

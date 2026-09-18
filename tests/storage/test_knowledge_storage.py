import pytest

from app.storage.knowledge import (
    KnowledgeObjectAccessError,
    KnowledgeObjectNotFoundError,
    LocalKnowledgeObjectStore,
)


@pytest.mark.asyncio
async def test_local_store_object_written_by_api_is_readable_by_worker(tmp_path):
    api_store = LocalKnowledgeObjectStore(tmp_path)
    worker_store = LocalKnowledgeObjectStore(tmp_path)

    object_key = await api_store.put_bytes(
        tenant_id="tenant-a",
        object_name="sentinel.txt",
        content=b"STAR_WAREHOUSE_KB_STORAGE_CONTRACT",
    )

    assert object_key == "tenant/tenant-a/sentinel.txt"
    assert await worker_store.read_bytes(tenant_id="tenant-a", object_key=object_key) == (
        b"STAR_WAREHOUSE_KB_STORAGE_CONTRACT"
    )


@pytest.mark.asyncio
async def test_local_store_rejects_cross_tenant_object_key(tmp_path):
    store = LocalKnowledgeObjectStore(tmp_path)
    object_key = await store.put_bytes(
        tenant_id="tenant-a",
        object_name="private.txt",
        content=b"tenant-a-only",
    )

    with pytest.raises(KnowledgeObjectAccessError):
        await store.read_bytes(tenant_id="tenant-b", object_key=object_key)


@pytest.mark.asyncio
async def test_local_store_missing_object_fails_deterministically(tmp_path):
    store = LocalKnowledgeObjectStore(tmp_path)

    with pytest.raises(
        KnowledgeObjectNotFoundError,
        match="Knowledge source object is missing: tenant/tenant-a/missing.txt",
    ):
        await store.read_bytes(
            tenant_id="tenant-a",
            object_key="tenant/tenant-a/missing.txt",
        )


@pytest.mark.asyncio
async def test_local_store_delete_is_idempotent_and_resync_read_fails(tmp_path):
    store = LocalKnowledgeObjectStore(tmp_path)
    object_key = await store.put_bytes(
        tenant_id="tenant-a",
        object_name="delete.txt",
        content=b"delete-me",
    )

    assert await store.delete(tenant_id="tenant-a", object_key=object_key) is True
    assert await store.delete(tenant_id="tenant-a", object_key=object_key) is False
    with pytest.raises(KnowledgeObjectNotFoundError):
        await store.read_bytes(tenant_id="tenant-a", object_key=object_key)


@pytest.mark.asyncio
async def test_object_name_rejects_platform_specific_path_separators(tmp_path):
    store = LocalKnowledgeObjectStore(tmp_path)

    with pytest.raises(ValueError, match="single safe path segment"):
        await store.put_bytes(
            tenant_id="tenant-a",
            object_name="..\\tenant-b\\source.txt",
            content=b"forbidden",
        )

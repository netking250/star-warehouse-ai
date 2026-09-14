import pytest
from qdrant_client import models

from app.core.tenancy import tenant_scope
from app.retrieval.client import QdrantKnowledgeClient


@pytest.mark.asyncio
async def test_ensure_collection_creates_collection(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()

    collections = await client.get_collections()
    assert knowledge_client.collection_name in [c.name for c in collections.collections]


@pytest.mark.asyncio
async def test_query_hybrid_returns_scored_points_with_payloads(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()

    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0], values=[1.0]),
                },
                payload={"content": "doc1", "source": "s1"},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": [0.2] * 1024,
                    "sparse": models.SparseVector(indices=[0], values=[1.0]),
                },
                payload={"content": "doc2", "source": "s2"},
            ),
        ]
    )

    results = await knowledge_client.query_hybrid(
        dense_vector=[0.1] * 1024,
        sparse_vector=models.SparseVector(indices=[0], values=[1.0]),
        limit=2,
    )

    assert len(results) == 2
    for r in results:
        assert r.payload is not None
        assert "content" in r.payload
        assert r.payload["tenant_id"] == "default"


@pytest.mark.asyncio
async def test_queries_never_return_another_tenants_chunks(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="", collection_name=collection_name, api_key="", client=client
    )
    await knowledge_client.ensure_collection()
    point = models.PointStruct(
        id=1,
        vector={
            "dense": [0.1] * 1024,
            "sparse": models.SparseVector(indices=[0], values=[1.0]),
        },
        payload={"content": "blue-only"},
    )
    with tenant_scope("tenant-blue"):
        await knowledge_client.upsert_chunks([point])
    with tenant_scope("tenant-green"):
        results = await knowledge_client.query_dense([0.1] * 1024)

    assert results == []


@pytest.mark.asyncio
async def test_query_ignores_more_similar_cross_tenant_chunk_and_delete_is_isolated(
    qdrant_client,
):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="", collection_name=collection_name, api_key="", client=client
    )
    await knowledge_client.ensure_collection()
    tenant_a_vector = [0.0] * 1024
    tenant_a_vector[1] = 1.0
    tenant_b_vector = [0.0] * 1024
    tenant_b_vector[0] = 1.0
    query_vector = tenant_b_vector

    with tenant_scope("tenant-a"):
        await knowledge_client.upsert_chunks(
            [
                models.PointStruct(
                    id="shared-document-1",
                    vector={
                        "dense": tenant_a_vector,
                        "sparse": models.SparseVector(indices=[1], values=[1.0]),
                    },
                    payload={"content": "tenant-a", "doc_id": 73},
                )
            ]
        )
    with tenant_scope("tenant-b"):
        await knowledge_client.upsert_chunks(
            [
                models.PointStruct(
                    id="shared-document-1",
                    vector={
                        "dense": tenant_b_vector,
                        "sparse": models.SparseVector(indices=[0], values=[1.0]),
                    },
                    payload={"content": "tenant-b", "doc_id": 73},
                )
            ]
        )

    with tenant_scope("tenant-a"):
        before_delete = await knowledge_client.query_dense(query_vector, limit=10)
        deleted = await knowledge_client.delete_document(73)
        after_delete = await knowledge_client.query_dense(query_vector, limit=10)
    with tenant_scope("tenant-b"):
        tenant_b_results = await knowledge_client.query_dense(query_vector, limit=10)

    assert all(point.payload is not None for point in before_delete)
    assert [point.payload["content"] for point in before_delete if point.payload] == ["tenant-a"]
    assert deleted is True
    assert after_delete == []
    assert all(point.payload is not None for point in tenant_b_results)
    assert [point.payload["content"] for point in tenant_b_results if point.payload] == ["tenant-b"]

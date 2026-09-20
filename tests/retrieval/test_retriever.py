import pytest
from qdrant_client import models

from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.reranker import RerankResult
from app.retrieval.retriever import HybridRetriever


class DeterministicRewriter:
    async def rewrite(self, query, **kwargs):
        return f"rewritten:{query}"

    async def rewrite_multi(self, query, **kwargs):
        return [query, f"variant:{query}"]

    def condense_history(self, conversation_history, query, memory_context=None):
        del memory_context
        history_text = " ".join(str(message.get("content", "")) for message in conversation_history)
        return f"{history_text} 当前问题：{query}"


class UnchangedRewriter(DeterministicRewriter):
    async def rewrite(self, query, **kwargs):
        return query


class UnexpectedRewrite(DeterministicRewriter):
    async def rewrite(self, query, **kwargs):
        raise AssertionError("deterministic follow-ups must precede model rewriting")


@pytest.mark.asyncio
async def test_contextualize_query_passes_prior_history_without_current_duplicate():
    class CapturingRewriter(DeterministicRewriter):
        def __init__(self):
            self.history = None

        async def rewrite(self, query, **kwargs):
            self.history = kwargs.get("conversation_history")
            return "Aurora Chair 有质量问题时，退货运费由谁承担？"

    rewriter = CapturingRewriter()
    retriever = HybridRetriever(None, None, None, None, rewriter)
    query = "那如果坏了呢？"
    prior_history = [
        {"role": "user", "content": "Aurora Chair 的退货期多久？"},
        {"role": "assistant", "content": "退货期是17个日历日。"},
    ]

    result = await retriever.contextualize_query(
        query,
        conversation_history=[*prior_history, {"role": "user", "content": query}],
    )

    assert result == "Aurora Chair 有质量问题时，退货运费由谁承担？"
    assert rewriter.history == prior_history


@pytest.mark.asyncio
async def test_contextualize_defect_follow_up_requests_return_shipping_policy():
    rewriter = UnexpectedRewrite()
    retriever = HybridRetriever(None, None, None, None, rewriter)
    query = "那如果是质量问题呢？"

    result = await retriever.contextualize_query(
        query,
        conversation_history=[
            {"role": "user", "content": "Aurora Chair 退货窗口多久？"},
            {"role": "assistant", "content": "退货窗口为17个日历日。"},
            {"role": "user", "content": query},
        ],
    )

    assert "Aurora Chair 退货窗口多久" in result
    assert "质量问题" in result
    assert "退货运费由谁承担" in result


@pytest.mark.asyncio
async def test_contextualize_query_condenses_history_when_model_keeps_elliptical_query():
    rewriter = UnexpectedRewrite()
    retriever = HybridRetriever(None, None, None, None, rewriter)
    query = "刚才说错了，是30个月。"

    result = await retriever.contextualize_query(
        query,
        conversation_history=[
            {"role": "user", "content": "Nova Desk 的保修多久？"},
            {"role": "assistant", "content": "保修期限为28个月。"},
            {"role": "user", "content": "我买了26个月。"},
            {"role": "assistant", "content": "26个月仍在保修期内。"},
            {"role": "user", "content": query},
        ],
    )

    assert "Nova Desk 的保修多久" in result
    assert "购买或使用时长为30个月" in result
    assert "替代之前" in result


@pytest.mark.asyncio
async def test_contextualize_weekday_follow_up_avoids_unsupported_calendar_projection():
    rewriter = UnexpectedRewrite()
    retriever = HybridRetriever(None, None, None, None, rewriter)
    query = "那如果是周一确认呢？"

    result = await retriever.contextualize_query(
        query,
        conversation_history=[
            {"role": "user", "content": "East Harbor 的订单通常多久出库？"},
            {"role": "assistant", "content": "订单确认后3个工作日内出库。"},
            {"role": "user", "content": query},
        ],
    )

    assert "East Harbor 的订单通常多久出库" in result
    assert "不推算" in result
    assert "具体星期日期" in result


class DeterministicDenseEmbedder:
    async def aembed_query(self, text):
        return [0.1] * 1024


class DeterministicSparseEmbedder:
    async def aembed(self, texts):
        return [models.SparseVector(indices=[0, 1], values=[1.0, 0.5]) for _ in texts]


class DeterministicReranker:
    async def rerank(self, query, documents, top_n=5):
        return [
            RerankResult(index=i, score=0.99 - i * 0.1) for i in range(min(top_n, len(documents)))
        ]


class FailingSparseEmbedder:
    async def aembed(self, texts):
        raise ConnectionError("sparse fail")


class FailingReranker:
    async def rerank(self, query, documents, top_n=5):
        raise ConnectionError("rerank fail")


class SingleResultReranker:
    async def rerank(self, query, documents, top_n=5):
        return [RerankResult(index=0, score=0.99)]


@pytest.mark.asyncio
async def test_retriever_orchestrates_all_steps(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    dense_vec_c1 = [0.1] * 1024
    dense_vec_c2 = [-0.5] * 1024
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": dense_vec_c1,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": dense_vec_c2,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c2", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert contents == {"c1", "c2"}
    for r in results:
        assert 0.0 <= r.score <= 1.0


@pytest.mark.asyncio
async def test_retriever_sparse_embedder_failure_propagates(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=FailingSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
    )

    with pytest.raises(ConnectionError, match="sparse fail"):
        await retriever.retrieve("怎么退货")


@pytest.mark.asyncio
async def test_retriever_reranker_failure_propagates(qdrant_client):
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
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=FailingReranker(),
        rewriter=DeterministicRewriter(),
    )

    with pytest.raises(ConnectionError, match="rerank fail"):
        await retriever.retrieve("怎么退货")


@pytest.mark.asyncio
async def test_retriever_multi_query_mode(qdrant_client):
    client, collection_name = qdrant_client
    knowledge_client = QdrantKnowledgeClient(
        url="",
        collection_name=collection_name,
        api_key="",
        client=client,
    )
    await knowledge_client.ensure_collection()
    dense_vec_c1 = [0.1] * 1024
    dense_vec_c2 = [-0.5] * 1024
    await knowledge_client.upsert_chunks(
        [
            models.PointStruct(
                id=1,
                vector={
                    "dense": dense_vec_c1,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c1", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": dense_vec_c2,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "c2", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=DeterministicReranker(),
        rewriter=DeterministicRewriter(),
        use_multi_query=True,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert contents == {"c1", "c2"}
    scores = [r.score for r in results]
    assert scores == pytest.approx([0.99, 0.89])


@pytest.mark.asyncio
async def test_retriever_multi_query_deduplicates(qdrant_client):
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
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "same", "source": "s1", "meta_data": {}},
            ),
            models.PointStruct(
                id=2,
                vector={
                    "dense": [0.1] * 1024,
                    "sparse": models.SparseVector(indices=[0, 1], values=[1.0, 0.5]),
                },
                payload={"content": "same", "source": "s2", "meta_data": {}},
            ),
        ]
    )

    retriever = HybridRetriever(
        qdrant_client=knowledge_client,
        dense_embedder=DeterministicDenseEmbedder(),
        sparse_embedder=DeterministicSparseEmbedder(),
        reranker=SingleResultReranker(),
        rewriter=DeterministicRewriter(),
        use_multi_query=True,
    )

    results = await retriever.retrieve("怎么退货")
    assert len(results) == 1
    assert results[0].content == "same"

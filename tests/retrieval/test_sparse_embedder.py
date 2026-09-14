import pytest
from fastembed.sparse.sparse_embedding_base import SparseEmbedding
from numpy import array
from qdrant_client import models

from app.retrieval.sparse_embedder import SparseTextEmbedder


class _DeterministicSparseEmbeddingProvider:
    def embed(self, documents, batch_size=256, parallel=None, **kwargs):
        del batch_size, parallel, kwargs
        texts = [documents] if isinstance(documents, str) else list(documents)
        return [
            SparseEmbedding(
                indices=array([0, index + 1]),
                values=array([1.0, float(len(text))]),
            )
            for index, text in enumerate(texts)
        ]


@pytest.mark.asyncio
async def test_sparse_embedder_produces_qdrant_sparse_vectors():
    embedder = SparseTextEmbedder(model=_DeterministicSparseEmbeddingProvider())
    texts = ["hello world", "电商退换货政策"]
    results = await embedder.aembed(texts)

    assert len(results) == 2
    for vec in results:
        assert isinstance(vec, models.SparseVector)
        assert len(vec.indices) > 0
        assert len(vec.values) > 0
        assert len(vec.indices) == len(vec.values)


def test_sparse_embedder_with_injected_provider_does_not_construct_fastembed(monkeypatch):
    def fail_if_constructed(*args, **kwargs):
        del args, kwargs
        raise AssertionError("external FastEmbed model construction was attempted")

    monkeypatch.setattr("app.retrieval.sparse_embedder.SparseTextEmbedding", fail_if_constructed)
    SparseTextEmbedder(model=_DeterministicSparseEmbeddingProvider())

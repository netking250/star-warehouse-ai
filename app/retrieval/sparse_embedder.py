import asyncio
from collections.abc import Iterable
from typing import Protocol

from fastembed import SparseTextEmbedding
from fastembed.sparse.sparse_embedding_base import SparseEmbedding
from qdrant_client import models

from app.core.config import settings


class SparseEmbeddingProvider(Protocol):
    """Provide sparse embeddings without prescribing a concrete model runtime."""

    def embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
        **kwargs: object,
    ) -> Iterable[SparseEmbedding]:
        """Return sparse embeddings for the supplied documents."""

        ...


class SparseTextEmbedder:
    def __init__(
        self,
        model_name: str = "Qdrant/bm25",
        model: SparseEmbeddingProvider | None = None,
    ) -> None:
        self.model_name = model_name
        if model is not None:
            self._model = model
        else:
            model_kwargs = {}
            if settings.FASTEMBED_CACHE_PATH:
                model_kwargs["cache_dir"] = settings.FASTEMBED_CACHE_PATH
            self._model = SparseTextEmbedding(model_name=self.model_name, **model_kwargs)

    def _embed_sync(self, texts: list[str]) -> list[models.SparseVector]:
        raw_embeddings = list(self._model.embed(texts))
        results = []
        for emb in raw_embeddings:
            indices = emb.indices.tolist()
            values = emb.values.tolist()
            results.append(models.SparseVector(indices=indices, values=values))
        return results

    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        return await asyncio.to_thread(self._embed_sync, texts)

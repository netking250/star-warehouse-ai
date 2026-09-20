import asyncio
import logging
import re

from pydantic import BaseModel

from app.core.cache import CacheManager
from app.core.config import settings

logger = logging.getLogger(__name__)

_POLICY_CONTEXT_PATTERN = re.compile(
    r"(?:保修|退货|退款|运费|出库|能退|warranty|return|refund|shipping|dispatch)",
    re.IGNORECASE,
)
_DURATION_PATTERN = re.compile(
    r"(?P<duration>\d+\s*(?:个?月|天|年|months?|days?|years?))",
    re.IGNORECASE,
)
_CORRECTION_PATTERN = re.compile(r"(?:说错|更正|改成|actually|correction)", re.IGNORECASE)
_WEEKDAY_PATTERN = re.compile(r"(?:周|星期)[一二三四五六日天]")
_DEFECT_PATTERN = re.compile(r"(?:质量问题|缺陷|瑕疵|损坏|defect|defective|damaged)", re.IGNORECASE)
_RETURN_POLICY_PATTERN = re.compile(r"(?:退货|return)", re.IGNORECASE)


class RetrievedChunk(BaseModel):
    content: str
    source: str
    score: float
    metadata: dict | None = None


class HybridRetriever:
    def __init__(
        self,
        qdrant_client,
        dense_embedder,
        sparse_embedder,
        reranker,
        rewriter,
        use_multi_query: bool = False,
        cache_manager: CacheManager | None = None,
    ):
        self.qdrant_client = qdrant_client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.reranker = reranker
        self.rewriter = rewriter
        self.use_multi_query = use_multi_query
        self._cache = cache_manager

    async def contextualize_query(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        memory_context: dict | None = None,
    ) -> str:
        """Rewrite an elliptical query using prior conversation messages only."""
        if not conversation_history:
            return query
        prior_history = list(conversation_history)
        latest = prior_history[-1]
        if (
            isinstance(latest, dict)
            and latest.get("role") == "user"
            and str(latest.get("content", "")).strip() == query.strip()
        ):
            prior_history.pop()
        if not prior_history:
            return query
        deterministic = self._deterministic_follow_up_query(query, prior_history)
        if deterministic is not None:
            return deterministic
        rewritten = await self.rewriter.rewrite(
            query,
            conversation_history=prior_history,
            memory_context=memory_context,
        )
        if rewritten.strip() != query.strip():
            return rewritten
        return self.rewriter.condense_history(
            prior_history,
            query,
            memory_context,
        )

    @staticmethod
    def _deterministic_follow_up_query(query: str, prior_history: list[dict]) -> str | None:
        """Resolve narrow policy follow-ups before stochastic rewriting."""
        policy_topic = next(
            (
                str(message.get("content", "")).strip()
                for message in reversed(prior_history)
                if message.get("role") == "user"
                and _POLICY_CONTEXT_PATTERN.search(str(message.get("content", "")))
            ),
            None,
        )
        if not policy_topic:
            return None

        duration_match = _DURATION_PATTERN.search(query)
        if duration_match:
            duration = duration_match.group("duration").replace(" ", "")
            if _CORRECTION_PATTERN.search(query):
                return (
                    f"同一会话中的政策主题：{policy_topic}\n"
                    f"用户更正其购买或使用时长为{duration}，以该最新时长替代之前的时长。"
                    "请依据知识库政策判断当前是否仍符合该政策。"
                )
            return (
                f"同一会话中的政策主题：{policy_topic}\n"
                f"用户说明其购买或使用时长为{duration}。"
                "请依据知识库政策判断当前是否仍符合该政策。"
            )

        if _WEEKDAY_PATTERN.search(query):
            return (
                f"同一会话中的政策主题：{policy_topic}\n"
                f"用户追问：{query}\n"
                "请仅陈述知识库中的正常时效，不推算或声称具体星期日期。"
            )
        if _DEFECT_PATTERN.search(query) and _RETURN_POLICY_PATTERN.search(policy_topic):
            return (
                f"同一会话中的政策主题：{policy_topic}\n"
                f"用户追问：{query}\n"
                "请检索商品存在质量问题时的退货政策，以及退货运费由谁承担。"
            )
        return None

    @staticmethod
    def _to_chunk(point, score: float) -> RetrievedChunk:
        payload = point.payload or {}
        return RetrievedChunk(
            content=str(payload.get("content", "")),
            source=str(payload.get("source", "unknown")),
            score=score,
            metadata=dict(payload.get("meta_data") or {}),
        )

    async def retrieve(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        memory_context: dict | None = None,
        variant_top_k: int | None = None,
        variant_reranker_enabled: bool | None = None,
    ) -> list[RetrievedChunk]:
        use_reranker = variant_reranker_enabled if variant_reranker_enabled is not None else True
        top_k = variant_top_k if variant_top_k is not None else settings.RETRIEVER_FINAL_TOPK

        if self._cache is not None and not self.use_multi_query:
            cached = await self._cache.get_retrieval(query)
            if cached is not None:
                return [RetrievedChunk.model_validate(c) for c in cached]

        if self.use_multi_query:
            variants = await self.rewriter.rewrite_multi(
                query,
                n=settings.RETRIEVER_MULTI_QUERY_N,
                conversation_history=conversation_history,
                memory_context=memory_context,
            )
            results = await asyncio.gather(
                *[self._retrieve_single(v, top_k, use_reranker) for v in variants]
            )
            all_chunks = self._deduplicate_chunks([c for r in results for c in r])
            if not all_chunks:
                return []
            if not use_reranker:
                return all_chunks[:top_k]
            documents = [c.content for c in all_chunks]
            reranked = await self.reranker.rerank(query, documents, top_n=top_k)
            final = []
            for r in reranked:
                if 0 <= r.index < len(all_chunks):
                    final.append(
                        RetrievedChunk(
                            content=all_chunks[r.index].content,
                            source=all_chunks[r.index].source,
                            score=r.score,
                            metadata=all_chunks[r.index].metadata,
                        )
                    )
            return final

        chunks = await self._retrieve_single(query, top_k, use_reranker)

        if self._cache is not None and not self.use_multi_query:
            try:
                await self._cache.set_retrieval(query, [c.model_dump() for c in chunks])
            except Exception as exc:
                logger.warning("Failed to cache retrieval result: %s", exc)

        return chunks

    async def _retrieve_single(
        self,
        query: str,
        top_k: int | None = None,
        use_reranker: bool = True,
    ) -> list[RetrievedChunk]:
        # Parallelize dense and sparse embedding generation to reduce latency.
        dense_task = self.dense_embedder.aembed_query(query)
        sparse_task = self.sparse_embedder.aembed([query])
        dense_vec, sparse_vecs = await asyncio.gather(dense_task, sparse_task)
        sparse_vec = sparse_vecs[0]

        final_top_k = top_k if top_k is not None else settings.RETRIEVER_FINAL_TOPK

        scored_points = await self.qdrant_client.query_hybrid(
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            dense_limit=settings.RETRIEVER_DENSE_TOPK,
            sparse_limit=settings.RETRIEVER_SPARSE_TOPK,
        )

        if not scored_points:
            return []

        documents = [str((p.payload or {}).get("content", "")) for p in scored_points]

        if not use_reranker:
            return [
                self._to_chunk(scored_points[i], 1.0)
                for i in range(min(final_top_k, len(scored_points)))
            ]

        reranked = await self.reranker.rerank(query, documents, top_n=final_top_k)

        results = []
        for r in reranked:
            if 0 <= r.index < len(scored_points):
                results.append(self._to_chunk(scored_points[r.index], r.score))

        return results

    @staticmethod
    def _deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for chunk in chunks:
            key = chunk.content.strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(chunk)
        return unique

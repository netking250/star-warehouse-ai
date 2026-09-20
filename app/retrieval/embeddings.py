import asyncio
import hashlib
import logging
import time

import httpx

from app.core.config import settings


class QwenEmbeddings:
    """通义千问 Embedding API 适配器"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        *,
        request_timeout_seconds: float = 10.0,
        failure_cooldown_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.request_timeout_seconds = request_timeout_seconds
        self.failure_cooldown_seconds = failure_cooldown_seconds
        self._cache: dict[str, list[float]] = {}
        self._inflight: dict[str, asyncio.Future[list[float]]] = {}
        self._state_lock = asyncio.Lock()
        self._failure_cooldown_until = 0.0

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        owned: list[tuple[int, str, str, asyncio.Future[list[float]]]] = []
        waiters: list[tuple[int, asyncio.Future[list[float]]]] = []
        zero_vector = [0.0] * self.dimensions

        async with self._state_lock:
            cooldown_active = time.monotonic() < self._failure_cooldown_until
            loop = asyncio.get_running_loop()
            for idx, text in enumerate(texts):
                key = self._cache_key(text)
                cached = self._cache.get(key)
                if cached is not None:
                    results[idx] = cached
                elif cooldown_active:
                    results[idx] = zero_vector.copy()
                elif key in self._inflight:
                    waiters.append((idx, self._inflight[key]))
                else:
                    future: asyncio.Future[list[float]] = loop.create_future()
                    self._inflight[key] = future
                    owned.append((idx, text, key, future))

        if owned:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "input": [text for _, text, _, _ in owned],
                            "dimensions": self.dimensions,
                        },
                        timeout=self.request_timeout_seconds,
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings = [item["embedding"] for item in data["data"]]
                    if len(embeddings) != len(owned):
                        raise ValueError("Embedding response count does not match request count")
                    async with self._state_lock:
                        for (idx, _text, key, future), emb in zip(owned, embeddings, strict=True):
                            self._cache[key] = emb
                            self._inflight.pop(key, None)
                            if not future.done():
                                future.set_result(emb)
                            results[idx] = emb
                except (httpx.HTTPError, OSError, ValueError):
                    logging.getLogger(__name__).warning(
                        "Embedding API call failed or timed out, returning zero vectors"
                    )
                    async with self._state_lock:
                        self._failure_cooldown_until = (
                            time.monotonic() + self.failure_cooldown_seconds
                        )
                        for idx, _text, key, future in owned:
                            fallback = zero_vector.copy()
                            self._inflight.pop(key, None)
                            if not future.done():
                                future.set_result(fallback)
                            results[idx] = fallback
                except asyncio.CancelledError:
                    async with self._state_lock:
                        for _idx, _text, key, future in owned:
                            self._inflight.pop(key, None)
                            if not future.done():
                                future.cancel()
                    raise

        for idx, future in waiters:
            results[idx] = await future

        return [result if result is not None else zero_vector.copy() for result in results]

    async def aembed_query(self, text: str) -> list[float]:
        results = await self.aembed_documents([text])
        return results[0]


def create_embedding_model() -> QwenEmbeddings:
    return QwenEmbeddings(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIM,
    )

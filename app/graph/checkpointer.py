"""Optimized Redis checkpointer with diff-based storage and compression."""

from __future__ import annotations

import copy
import json
import logging
import zlib
from collections.abc import AsyncIterator, Sequence
from typing import Any, override

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from langgraph.checkpoint.redis import AsyncRedisSaver

from app.core.tenancy import namespaced_key
from app.observability.metrics import record_checkpoint_cleanup

logger = logging.getLogger(__name__)

_DEFAULT_TTL_DAYS = 30
_DEFAULT_BASE_EVERY = 10
_DEFAULT_COMPRESSION_LEVEL = 6


class OptimizedRedisCheckpoint(BaseCheckpointSaver):
    def __init__(
        self,
        redis_client: Any,
        ttl_days: int = _DEFAULT_TTL_DAYS,
        base_every: int = _DEFAULT_BASE_EVERY,
        compression_level: int = _DEFAULT_COMPRESSION_LEVEL,
    ) -> None:
        super().__init__()
        self._redis = redis_client
        self._base_saver = AsyncRedisSaver(redis_client=redis_client)
        self._ttl_seconds = ttl_days * 24 * 3600
        self._base_every = max(1, base_every)
        self._compression_level = compression_level

    async def setup(self) -> None:
        await self._base_saver.setup()

    async def aput(
        self,
        config: Any,
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
        stream_mode: str = "values",
    ) -> Any:
        # The legacy JSON diff format coerced LangGraph channel-version values to
        # strings and could make resumed graphs compare ``str`` with ``int``.
        # Keep persistence authoritative and typed through the upstream saver.
        return await self._base_saver.aput(config, checkpoint, metadata, new_versions, stream_mode)

    async def aget(self, config: Any) -> Any:
        tup = await self.aget_tuple(config)
        return tup.checkpoint if tup is not None else None

    async def aget_tuple(self, config: Any) -> CheckpointTuple | None:
        # Do not read legacy optimized checkpoints: their JSON representation is
        # not type safe. Existing keys remain available for explicit cleanup.
        return await self._base_saver.aget_tuple(config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,  # noqa: A002
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        async for checkpoint in self._base_saver.alist(
            config, filter=filter, before=before, limit=limit
        ):
            yield checkpoint

    @override
    async def aprune(self, thread_ids: Sequence[str], *, strategy: str = "keep_latest") -> None:
        await self._base_saver.aprune(thread_ids, strategy=strategy)

        for thread_id in thread_ids:
            async for key in self._redis.scan_iter(
                match=namespaced_key(f"ckpt_index:{thread_id}:*")
            ):
                key_str = key.decode() if isinstance(key, bytes) else key
                ns = key_str.split(":", 2)[2]
                await self._prune_optimized(thread_id, ns, strategy)

    @staticmethod
    def _compute_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
        diff: dict[str, Any] = {}
        for key, new_val in new.items():
            if key not in old:
                diff[key] = new_val
            elif old[key] != new_val:
                if isinstance(new_val, dict) and isinstance(old[key], dict):
                    nested = OptimizedRedisCheckpoint._compute_diff(old[key], new_val)
                    if nested:
                        diff[key] = nested
                else:
                    diff[key] = new_val
        for key in old:
            if key not in new:
                diff[key] = {"__deleted__": True}
        return diff

    @staticmethod
    def _apply_diff(base: dict[str, Any], diff: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(base)
        for key, val in diff.items():
            if isinstance(val, dict) and val.get("__deleted__") is True:
                result.pop(key, None)
            else:
                result[key] = val
        return result

    async def _reconstruct_from_opt(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str | None,
        compressed: bytes,
    ) -> dict[str, Any] | None:
        try:
            raw = zlib.decompress(compressed)
            payload = json.loads(raw.decode("utf-8"))
        except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Failed to decode optimised checkpoint: %s", exc)
            return None

        if payload.get("__base__"):
            return payload["data"]

        parent_id = payload.get("parent_id", "")
        diff_chain: list[dict[str, Any]] = [payload["diff"]]
        visited: set[str] = {checkpoint_id or ""}

        while parent_id:
            if parent_id in visited:
                logger.warning("Cycle detected in checkpoint diff chain")
                return None
            visited.add(parent_id)

            parent_key = self._opt_key(thread_id, checkpoint_ns, parent_id)
            parent_compressed = await self._redis.get(parent_key)
            if parent_compressed is None:
                logger.warning("Missing parent checkpoint %s for thread %s", parent_id, thread_id)
                return None

            try:
                parent_raw = zlib.decompress(parent_compressed)
                parent_payload = json.loads(parent_raw.decode("utf-8"))
            except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning("Failed to decode parent checkpoint: %s", exc)
                return None

            if parent_payload.get("__base__"):
                base_checkpoint = parent_payload["data"]
                for d in reversed(diff_chain):
                    base_checkpoint = self._apply_diff(base_checkpoint, d)
                return base_checkpoint

            parent_id = parent_payload.get("parent_id", "")
            diff_chain.append(parent_payload["diff"])

        logger.warning("Could not find base checkpoint for %s", checkpoint_id)
        return None

    async def _prune_optimized(self, thread_id: str, checkpoint_ns: str, strategy: str) -> None:
        index_key = self._index_key(thread_id, checkpoint_ns)
        if strategy == "keep_latest":
            ids = await self._redis.zrange(index_key, 0, -1)
            if len(ids) > 1:
                to_remove = ids[:-1]
                pipe = self._redis.pipeline()
                for cid in to_remove:
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    pipe.delete(self._opt_key(thread_id, checkpoint_ns, cid_str))
                pipe.zrem(index_key, *to_remove)
                await pipe.execute()
                record_checkpoint_cleanup(len(to_remove))
        else:
            ids = await self._redis.zrange(index_key, 0, -1)
            if ids:
                pipe = self._redis.pipeline()
                for cid in ids:
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    pipe.delete(self._opt_key(thread_id, checkpoint_ns, cid_str))
                pipe.delete(index_key)
                await pipe.execute()
                record_checkpoint_cleanup(len(ids))

    @staticmethod
    def _opt_key(thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return namespaced_key(f"ckpt_opt:{thread_id}:{checkpoint_ns}:{checkpoint_id}")

    @staticmethod
    def _index_key(thread_id: str, checkpoint_ns: str) -> str:
        return namespaced_key(f"ckpt_index:{thread_id}:{checkpoint_ns}")

    def get_next_version(self, current: Any | None, channel: Any = None) -> Any:
        """Generate a Redis-compatible monotonically increasing version."""
        return self._base_saver.get_next_version(current, channel)

    async def aput_writes(
        self,
        config: Any,
        writes: Any,
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Write pending writes to the checkpointer.

        Delegates to the base saver for write persistence.
        """
        try:
            await self._base_saver.aput_writes(config, writes, task_id, task_path)
        except Exception:
            logger.exception("Base saver aput_writes failed (non-critical)")

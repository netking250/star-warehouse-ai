"""Regression coverage for RedisVL checkpointer cleanup ownership."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.redis import AsyncRedisSaver
from redis.asyncio import Redis

from app.core.config import settings
from tests._redisvl import cleanup_redisvl_resources


def _redis_client(db: int) -> Redis:
    """Create a Redis client for one explicitly selected test database."""
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=db,
        password=settings.REDIS_PASSWORD.get_secret_value(),
        decode_responses=True,
    )


async def _write_checkpoint(
    saver: AsyncRedisSaver,
    thread_id: str,
    checkpoint_id: str,
    task_id: str,
) -> None:
    """Write one checkpoint and pending write through the real saver."""
    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint: Checkpoint = {
        "v": 1,
        "id": checkpoint_id,
        "ts": datetime.now(UTC).isoformat(),
        "channel_values": {"messages": []},
        "channel_versions": {},
        "versions_seen": {},
        "updated_channels": None,
    }
    metadata: CheckpointMetadata = {}
    channel_versions: ChannelVersions = {}
    saved_config = await saver.aput(config, checkpoint, metadata, channel_versions)
    await saver.aput_writes(saved_config, [("messages", "cleanup-write")], task_id)


@pytest.mark.asyncio
async def test_redisvl_cleanup_removes_registry_keys_and_preserves_sentinel() -> None:
    """Checkpointer teardown removes only resources owned by its run."""
    client = _redis_client(0)
    generic_client = _redis_client(15)
    run_id = uuid.uuid4().hex
    checkpoint_prefix = f"test_cleanup_checkpoint_{run_id}"
    checkpoint_write_prefix = f"{checkpoint_prefix}_write"
    thread_id = f"cleanup-thread-{run_id}"
    checkpoint_id = f"cleanup-checkpoint-{run_id}"
    sentinel_key = f"t09:redisvl-sentinel:{run_id}"
    saver = AsyncRedisSaver(
        redis_client=client,
        checkpoint_prefix=checkpoint_prefix,
        checkpoint_write_prefix=checkpoint_write_prefix,
    )

    try:
        await client.set(sentinel_key, "preserve")
        await generic_client.set(sentinel_key, "generic-preserve")
        await saver.setup()
        await _write_checkpoint(saver, thread_id, checkpoint_id, "cleanup-task")

        await cleanup_redisvl_resources(
            client,
            saver,
            checkpoint_prefix=checkpoint_prefix,
            checkpoint_write_prefix=checkpoint_write_prefix,
        )

        assert await client.exists(sentinel_key) == 1
        assert await generic_client.get(sentinel_key) == "generic-preserve"
        assert await client.exists(f"checkpoint_latest:{thread_id}:__empty__") == 0
        assert await client.exists(f"write_keys_zset:{thread_id}:__empty__:{checkpoint_id}") == 0
        assert [key async for key in client.scan_iter(match=f"{checkpoint_prefix}:*")] == []
        assert [key async for key in client.scan_iter(match=f"{checkpoint_write_prefix}:*")] == []
    finally:
        await cleanup_redisvl_resources(
            client,
            saver,
            checkpoint_prefix=checkpoint_prefix,
            checkpoint_write_prefix=checkpoint_write_prefix,
        )
        await client.delete(sentinel_key)
        await generic_client.delete(sentinel_key)
        await client.aclose()
        await generic_client.aclose()


@pytest.mark.asyncio
async def test_redisvl_cleanup_preserves_another_run_registry_members() -> None:
    """Check cleanup cannot remove a concurrent run's shared registry member."""
    client = _redis_client(0)
    shared_thread_id = f"shared-thread-{uuid.uuid4().hex}"
    shared_checkpoint_id = f"shared-checkpoint-{uuid.uuid4().hex}"
    run_a = uuid.uuid4().hex
    run_b = uuid.uuid4().hex
    prefix_a = f"test_cleanup_checkpoint_{run_a}"
    prefix_b = f"test_cleanup_checkpoint_{run_b}"
    write_prefix_a = f"{prefix_a}_write"
    write_prefix_b = f"{prefix_b}_write"
    saver_a = AsyncRedisSaver(
        redis_client=client,
        checkpoint_prefix=prefix_a,
        checkpoint_write_prefix=write_prefix_a,
    )
    saver_b = AsyncRedisSaver(
        redis_client=client,
        checkpoint_prefix=prefix_b,
        checkpoint_write_prefix=write_prefix_b,
    )

    try:
        await saver_a.setup()
        await saver_b.setup()
        await _write_checkpoint(saver_a, shared_thread_id, shared_checkpoint_id, "task-a")
        await _write_checkpoint(saver_b, shared_thread_id, shared_checkpoint_id, "task-b")

        await cleanup_redisvl_resources(
            client,
            saver_a,
            checkpoint_prefix=prefix_a,
            checkpoint_write_prefix=write_prefix_a,
        )

        assert await saver_b.checkpoints_index.exists()
        assert [key async for key in client.scan_iter(match=f"{prefix_a}:*")] == []
        assert [key async for key in client.scan_iter(match=f"{write_prefix_a}:*")] == []
        pointer = await client.get(f"checkpoint_latest:{shared_thread_id}:__empty__")
        assert isinstance(pointer, str) and pointer.startswith(f"{prefix_b}:")
        registry_key = f"write_keys_zset:{shared_thread_id}:__empty__:{shared_checkpoint_id}"
        members = await client.zrange(registry_key, 0, -1)
        assert members and all(member.startswith(f"{write_prefix_b}:") for member in members)
    finally:
        await cleanup_redisvl_resources(
            client,
            saver_a,
            checkpoint_prefix=prefix_a,
            checkpoint_write_prefix=write_prefix_a,
        )
        await cleanup_redisvl_resources(
            client,
            saver_b,
            checkpoint_prefix=prefix_b,
            checkpoint_write_prefix=write_prefix_b,
        )
        await client.aclose()


@pytest.mark.asyncio
async def test_redisvl_cleanup_repeated_runs_do_not_accumulate_registry_keys() -> None:
    """Check sequential RedisVL lifecycles leave no registry accumulation."""
    client = _redis_client(0)
    run_resources: list[tuple[AsyncRedisSaver, str, str]] = []

    try:
        for _ in range(2):
            run_id = uuid.uuid4().hex
            checkpoint_prefix = f"test_cleanup_checkpoint_{run_id}"
            checkpoint_write_prefix = f"{checkpoint_prefix}_write"
            thread_id = f"repeated-thread-{run_id}"
            checkpoint_id = f"repeated-checkpoint-{run_id}"
            saver = AsyncRedisSaver(
                redis_client=client,
                checkpoint_prefix=checkpoint_prefix,
                checkpoint_write_prefix=checkpoint_write_prefix,
            )
            run_resources.append((saver, checkpoint_prefix, checkpoint_write_prefix))
            await saver.setup()
            await _write_checkpoint(saver, thread_id, checkpoint_id, "repeated-task")
            await cleanup_redisvl_resources(
                client,
                saver,
                checkpoint_prefix=checkpoint_prefix,
                checkpoint_write_prefix=checkpoint_write_prefix,
            )

            assert [key async for key in client.scan_iter(match=f"{checkpoint_prefix}:*")] == []
            assert [
                key async for key in client.scan_iter(match=f"{checkpoint_write_prefix}:*")
            ] == []
            assert await client.exists(f"checkpoint_latest:{thread_id}:__empty__") == 0
            assert (
                await client.exists(f"write_keys_zset:{thread_id}:__empty__:{checkpoint_id}") == 0
            )
    finally:
        for saver, checkpoint_prefix, checkpoint_write_prefix in run_resources:
            await cleanup_redisvl_resources(
                client,
                saver,
                checkpoint_prefix=checkpoint_prefix,
                checkpoint_write_prefix=checkpoint_write_prefix,
            )
        await client.aclose()

"""Test-only RedisVL resource lifecycle helpers."""

from __future__ import annotations

from langgraph.checkpoint.redis import AsyncRedisSaver
from redis.asyncio import Redis


async def cleanup_redisvl_resources(
    client: Redis,
    saver: AsyncRedisSaver,
    *,
    checkpoint_prefix: str,
    checkpoint_write_prefix: str,
) -> None:
    """Remove one checkpointer run without touching unrelated Redis data."""
    for index in (saver.checkpoints_index, saver.checkpoint_writes_index):
        if await index.exists():
            await index.delete(drop=True)

    await _delete_prefixed_keys(client, checkpoint_prefix)
    await _delete_prefixed_keys(client, checkpoint_write_prefix)
    await _delete_owned_latest_pointers(client, checkpoint_prefix)
    await _remove_owned_write_registry_members(client, checkpoint_write_prefix)


async def _delete_prefixed_keys(client: Redis, prefix: str) -> None:
    """Delete keys whose full name starts with one run-owned prefix."""
    keys = [key async for key in client.scan_iter(match=f"{prefix}:*")]
    if keys:
        await client.delete(*keys)


async def _delete_owned_latest_pointers(client: Redis, checkpoint_prefix: str) -> None:
    """Delete latest pointers only when their value references this run."""
    run_marker = f"{checkpoint_prefix}:"
    pointer_keys = [key async for key in client.scan_iter(match="checkpoint_latest:*")]
    for pointer_key in pointer_keys:
        pointer_value = await client.get(pointer_key)
        if isinstance(pointer_value, bytes):
            pointer_value = pointer_value.decode()
        if isinstance(pointer_value, str) and pointer_value.startswith(run_marker):
            await client.delete(pointer_key)


async def _remove_owned_write_registry_members(client: Redis, checkpoint_write_prefix: str) -> None:
    """Remove only this run's members from globally named write registries."""
    run_marker = f"{checkpoint_write_prefix}:"
    registry_keys = [key async for key in client.scan_iter(match="write_keys_zset:*")]
    for registry_key in registry_keys:
        members = await client.zrange(registry_key, 0, -1)
        owned_members = [
            member.decode() if isinstance(member, bytes) else member
            for member in members
            if (member.decode() if isinstance(member, bytes) else member).startswith(run_marker)
        ]
        if owned_members:
            await client.zrem(registry_key, *owned_members)
            if await client.zcard(registry_key) == 0:
                await client.delete(registry_key)

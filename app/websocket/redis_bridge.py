"""Redis pub/sub bridge for WebSocket broadcasting across processes."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisBroadcastBridge:
    """Minimal Redis pub/sub bridge for cross-process WebSocket broadcasts."""

    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, event: str, data: dict[str, Any], room: str) -> None:
        """Publish a JSON payload to the Redis channel for the given room."""
        channel = f"ws:room:{room}"
        payload = json.dumps({"event": event, "data": data, "room": room})
        try:
            await self._redis.publish(channel, payload)
        except (RedisError, ConnectionError, OSError) as exc:
            logger.error(
                "Failed to publish WebSocket message to Redis",
                extra={
                    "event": "websocket_redis_publish_failure",
                    "error_type": type(exc).__name__,
                },
            )

    async def subscribe(self, room: str) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator that listens to the Redis channel for the given room."""
        channel = f"ws:room:{room}"
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
        except (RedisError, ConnectionError, OSError) as exc:
            logger.error(
                "Failed to subscribe to Redis",
                extra={
                    "event": "websocket_redis_subscribe_failure",
                    "error_type": type(exc).__name__,
                },
            )
            return

        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except json.JSONDecodeError:
                        logger.warning(
                            "Invalid JSON in Redis pubsub message",
                            extra={"event": "websocket_redis_invalid_message"},
                        )
                        continue
                    yield payload
        except (RedisError, ConnectionError, OSError) as exc:
            logger.error(
                "Error in Redis pubsub listener",
                extra={
                    "event": "websocket_redis_listener_failure",
                    "error_type": type(exc).__name__,
                },
            )
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except (RedisError, OSError) as exc:
                logger.error(
                    "Error closing Redis pubsub",
                    extra={
                        "event": "websocket_redis_close_failure",
                        "error_type": type(exc).__name__,
                    },
                )

    async def close(self) -> None:
        """Close the underlying Redis client."""
        try:
            await self._redis.aclose()
        except (RedisError, OSError) as exc:
            logger.error(
                "Error closing Redis client",
                extra={
                    "event": "websocket_redis_client_close_failure",
                    "error_type": type(exc).__name__,
                },
            )

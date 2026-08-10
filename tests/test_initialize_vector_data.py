"""Tests for idempotent vector-data initialization."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.initialize_vector_data import _tenant_data_exists


@pytest.mark.asyncio
async def test_tenant_data_exists_false_when_collection_is_missing():
    client = AsyncMock()
    client.collection_exists.return_value = False

    assert not await _tenant_data_exists(client, "development_knowledge_chunks")
    client.count.assert_not_awaited()


@pytest.mark.asyncio
async def test_tenant_data_exists_counts_only_active_tenant():
    client = AsyncMock()
    client.collection_exists.return_value = True
    client.count.return_value = SimpleNamespace(count=3)

    assert await _tenant_data_exists(client, "development_knowledge_chunks")
    count_filter = client.count.await_args.kwargs["count_filter"]
    assert count_filter.must[0].key == "tenant_id"
    assert count_filter.must[0].match.value == "default"

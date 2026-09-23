"""Tests for legacy bootstrap compatibility wrappers."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts import initialize_vector_data, seed_data, seed_product_catalog


@pytest.mark.asyncio
async def test_initialize_vector_data_delegates_to_canonical_bootstrap(monkeypatch) -> None:
    bootstrap = AsyncMock()
    monkeypatch.setattr(initialize_vector_data, "bootstrap_main", bootstrap)

    await initialize_vector_data.main()

    bootstrap.assert_awaited_once_with(Path("data"))


@pytest.mark.asyncio
async def test_seed_data_delegates_to_canonical_bootstrap(monkeypatch) -> None:
    bootstrap = AsyncMock()
    monkeypatch.setattr(seed_data, "bootstrap_main", bootstrap)

    await seed_data.seed_data()

    bootstrap.assert_awaited_once_with(Path("data"))


@pytest.mark.asyncio
async def test_seed_product_catalog_delegates_to_canonical_bootstrap(monkeypatch) -> None:
    bootstrap = AsyncMock()
    monkeypatch.setattr(seed_product_catalog, "bootstrap_main", bootstrap)

    await seed_product_catalog.main()

    bootstrap.assert_awaited_once_with(Path("data"))

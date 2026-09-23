"""Run the canonical persisted local development and UAT data bootstrap."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

from app.bootstrap.local_data import LocalBootstrapConfig, bootstrap_local_data
from app.core.config import settings


def _configured_bootstrap() -> LocalBootstrapConfig:
    """Build the local-only bootstrap contract from centralized settings."""
    return LocalBootstrapConfig(
        enabled=settings.LOCAL_BOOTSTRAP_ENABLED,
        environment=settings.ENVIRONMENT,
        tenant_id=settings.LOCAL_BOOTSTRAP_TENANT_ID,
        tenant_name=settings.LOCAL_BOOTSTRAP_TENANT_NAME,
        customer_username=settings.LOCAL_BOOTSTRAP_CUSTOMER_USERNAME,
        customer_password=settings.LOCAL_BOOTSTRAP_CUSTOMER_PASSWORD,
        customer_email=settings.LOCAL_BOOTSTRAP_CUSTOMER_EMAIL,
        admin_username=settings.LOCAL_BOOTSTRAP_ADMIN_USERNAME,
        admin_password=settings.LOCAL_BOOTSTRAP_ADMIN_PASSWORD,
        admin_email=settings.LOCAL_BOOTSTRAP_ADMIN_EMAIL,
    )


async def main(data_dir: Path) -> None:
    """Run the bootstrap and print only its non-secret verification report."""
    report = await bootstrap_local_data(_configured_bootstrap(), data_dir=data_dir)
    print(json.dumps(asdict(report), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create or reconcile persisted local/UAT development data."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Repository-owned knowledge source directory.",
    )
    arguments = parser.parse_args()
    asyncio.run(main(arguments.data_dir))

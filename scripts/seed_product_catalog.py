"""Compatibility wrapper for the canonical local bootstrap command."""

import asyncio
from pathlib import Path

from scripts.bootstrap_local_data import main as bootstrap_main


async def main() -> None:
    """Run the canonical guarded local data bootstrap."""
    await bootstrap_main(Path("data"))


if __name__ == "__main__":
    asyncio.run(main())

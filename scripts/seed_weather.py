"""Seed/refresh the preset weather library from data/weather/*.epw.

Usage (from repo root or anywhere):

    uv --directory backend run python ../scripts/seed_weather.py

This script does not delete user-uploaded weather files. It only inserts
new EPW files found under data/weather/ that are not yet recorded in DB.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.database import async_session, engine, Base  # noqa: E402
from app.services.library_service import seed_preset_weather  # noqa: E402


async def _run() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await seed_preset_weather(session)
    print("Weather seeding done (data/weather/*.epw scanned).")


if __name__ == "__main__":
    asyncio.run(_run())

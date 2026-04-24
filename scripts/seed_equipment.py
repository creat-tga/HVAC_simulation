"""Sync the equipment library from data/equipment/*.json into the backend DB.

Usage (run from repo root or anywhere):

    # default: read .env in backend/ and write to its database
    uv --directory backend run python ../scripts/seed_equipment.py

    # override data dir
    uv --directory backend run python ../scripts/seed_equipment.py --data-dir d:/path/to/equipment

This script does NOT require the SEED_EQUIPMENT_FROM_DATA flag — it always
performs the sync. The flag in .env only controls whether the backend
auto-syncs on startup.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running this file directly: add backend/ to sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.database import async_session, engine, Base  # noqa: E402
from app.services.library_service import sync_equipment_from_data  # noqa: E402


async def _run(data_dir: Path | None) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        counts = await sync_equipment_from_data(session, data_dir)
    print(
        "Equipment sync done: "
        f"files={counts['files']} deleted={counts.get('deleted', 0)} "
        f"inserted={counts['inserted']} updated={counts['updated']} "
        f"skipped={counts['skipped']}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Seed/sync equipment library from JSON.")
    p.add_argument(
        "--data-dir",
        type=str,
        default="",
        help="Override data directory (defaults to <repo_root>/data/equipment).",
    )
    args = p.parse_args()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else None
    asyncio.run(_run(data_dir))


if __name__ == "__main__":
    main()

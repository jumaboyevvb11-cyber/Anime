"""Xabar yuborish tarixi."""
from __future__ import annotations

from typing import Any

from bot.services.database import Database
from bot.utils import timefmt

Row = dict[str, Any]


class BroadcastsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create(self, admin_id: int, kind: str, preview: str, total: int) -> int:
        return await self.db.fetchval(
            "INSERT INTO broadcasts (admin_id, kind, preview, total, started_at) "
            "VALUES ($1,$2,$3,$4,$5) RETURNING id",
            admin_id, kind, preview[:200], total, timefmt.now(),
        )

    async def progress(self, bid: int, sent: int, failed: int, blocked: int) -> None:
        await self.db.execute(
            "UPDATE broadcasts SET sent=$2, failed=$3, blocked=$4 WHERE id=$1",
            bid, sent, failed, blocked)

    async def finish(self, bid: int, status: str, sent: int, failed: int, blocked: int) -> None:
        await self.db.execute(
            "UPDATE broadcasts SET status=$2, sent=$3, failed=$4, blocked=$5, finished_at=$6 "
            "WHERE id=$1", bid, status, sent, failed, blocked, timefmt.now())

    async def get(self, bid: int) -> Row | None:
        return await self.db.fetchrow("SELECT * FROM broadcasts WHERE id=$1", bid)

    async def recent(self, limit: int = 10) -> list[Row]:
        return await self.db.fetch(
            "SELECT * FROM broadcasts ORDER BY id DESC LIMIT $1", limit)

    async def count(self) -> int:
        return await self.db.fetchval("SELECT count(*) FROM broadcasts") or 0

    async def mark_interrupted(self) -> int:
        return await self.db.execute(
            "UPDATE broadcasts SET status='interrupted', finished_at=$1 WHERE status='running'",
            timefmt.now())

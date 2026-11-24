"""Foydalanuvchilar jadvali."""
from __future__ import annotations

from typing import Any

from bot.services.database import Database
from bot.utils import timefmt

Row = dict[str, Any]


class UsersRepo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.blocked: set[int] = set()  # xotirada: har xabarda bazaga bormaslik uchun

    async def load(self) -> None:
        rows = await self.db.fetch("SELECT user_id FROM users WHERE is_blocked=1")
        self.blocked = {r["user_id"] for r in rows}

    async def upsert(self, user_id: int, name: str, username: str | None) -> None:
        now = timefmt.now()
        await self.db.execute(
            "INSERT INTO users (user_id, name, username, joined_at, last_active) "
            "VALUES ($1,$2,$3,$4,$4) "
            "ON CONFLICT (user_id) DO UPDATE SET name=excluded.name, "
            "username=excluded.username, last_active=excluded.last_active, bot_blocked=0",
            user_id, name[:100], username, now,
        )

    async def get(self, user_id: int) -> Row | None:
        return await self.db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)

    async def find(self, query: str) -> Row | None:
        """Telegram ID yoki @username bo'yicha qidirish."""
        query = query.strip()
        if query.lstrip("-").isdigit():
            return await self.get(int(query))
        uname = query.lstrip("@").casefold()
        if not uname:
            return None
        return await self.db.fetchrow(
            "SELECT * FROM users WHERE lower(username)=$1", uname
        )

    @staticmethod
    def _where(flt: str) -> str:
        return {"blk": "WHERE is_blocked=1", "new": f"WHERE joined_at >= {timefmt.day_start()}"}.get(flt, "")

    async def count(self, flt: str = "all") -> int:
        return await self.db.fetchval(f"SELECT count(*) FROM users {self._where(flt)}") or 0

    async def page(self, flt: str, limit: int, offset: int) -> list[Row]:
        return await self.db.fetch(
            f"SELECT * FROM users {self._where(flt)} "
            "ORDER BY last_active DESC, user_id LIMIT $1 OFFSET $2",
            limit, offset,
        )

    async def set_blocked(self, user_id: int, blocked: bool, by: int | None) -> bool:
        if blocked:
            n = await self.db.execute(
                "UPDATE users SET is_blocked=1, blocked_at=$2, blocked_by=$3 WHERE user_id=$1",
                user_id, timefmt.now(), by,
            )
        else:
            n = await self.db.execute(
                "UPDATE users SET is_blocked=0, blocked_at=NULL, blocked_by=NULL WHERE user_id=$1",
                user_id,
            )
        if n:
            (self.blocked.add if blocked else self.blocked.discard)(user_id)
        return bool(n)

    async def mark_bot_blocked(self, ids: list[int]) -> None:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join(f"${n + 1}" for n in range(len(chunk)))
            await self.db.execute(
                f"UPDATE users SET bot_blocked=1 WHERE user_id IN ({marks})", *chunk
            )

    async def broadcast_ids(self) -> list[int]:
        rows = await self.db.fetch(
            "SELECT user_id FROM users WHERE is_blocked=0 AND bot_blocked=0 ORDER BY user_id"
        )
        return [r["user_id"] for r in rows]

    # ---- statistika ----
    async def total(self) -> int:
        return await self.count("all")

    async def new_since(self, ts: int) -> int:
        return await self.db.fetchval("SELECT count(*) FROM users WHERE joined_at >= $1", ts) or 0

    async def active_since(self, ts: int) -> int:
        return await self.db.fetchval("SELECT count(*) FROM users WHERE last_active >= $1", ts) or 0

    async def blocked_count(self) -> int:
        return await self.count("blk")

    async def bot_blocked_count(self) -> int:
        return await self.db.fetchval("SELECT count(*) FROM users WHERE bot_blocked=1") or 0

    async def daily_new(self, since: int) -> dict[int, int]:
        """{kun_raqami: soni} — kun raqami mahalliy vaqt bo'yicha."""
        off = timefmt.tz_offset_seconds()
        rows = await self.db.fetch(
            "SELECT (joined_at + $1) / 86400 AS d, count(*) AS c FROM users "
            "WHERE joined_at >= $2 GROUP BY d ORDER BY d", off, since,
        )
        return {r["d"]: r["c"] for r in rows}

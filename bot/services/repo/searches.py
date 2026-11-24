"""Qidiruvlar, anime ko'rishlar va umumiy hisoblagichlar."""
from __future__ import annotations

import re
from typing import Any

from bot.services.database import Database
from bot.utils import timefmt

Row = dict[str, Any]


def normalize(term: str) -> str:
    return re.sub(r"\s+", " ", term).strip().casefold()[:100]


class SearchesRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def log(self, user_id: int, term: str, results: int) -> None:
        await self.db.execute(
            "INSERT INTO search_logs (user_id, term, results, ts) VALUES ($1,$2,$3,$4)",
            user_id, normalize(term), results, timefmt.now(),
        )
        await self.db.execute(
            "INSERT INTO counters (name, val) VALUES ('searches', 1) "
            "ON CONFLICT (name) DO UPDATE SET val = counters.val + 1"
        )

    async def track_view(self, anime_id: int, title: str) -> None:
        await self.db.execute(
            "INSERT INTO anime_stats (anime_id, title, views, last_ts) VALUES ($1,$2,1,$3) "
            "ON CONFLICT (anime_id) DO UPDATE SET views = anime_stats.views + 1, "
            "title=excluded.title, last_ts=excluded.last_ts",
            anime_id, title[:200], timefmt.now(),
        )

    async def total(self) -> int:
        return await self.db.fetchval("SELECT val FROM counters WHERE name='searches'") or 0

    async def count_since(self, ts: int) -> int:
        return await self.db.fetchval("SELECT count(*) FROM search_logs WHERE ts >= $1", ts) or 0

    async def unique_users_since(self, ts: int) -> int:
        return await self.db.fetchval(
            "SELECT count(DISTINCT user_id) FROM search_logs WHERE ts >= $1", ts
        ) or 0

    async def top_terms(self, since: int, limit: int = 10) -> list[Row]:
        return await self.db.fetch(
            "SELECT term, count(*) AS c FROM search_logs WHERE ts >= $1 "
            "GROUP BY term ORDER BY c DESC, term LIMIT $2", since, limit,
        )

    async def top_animes(self, limit: int = 10) -> list[Row]:
        return await self.db.fetch(
            "SELECT anime_id, title, views FROM anime_stats ORDER BY views DESC, title LIMIT $1",
            limit,
        )

    async def daily(self, since: int) -> dict[int, int]:
        off = timefmt.tz_offset_seconds()
        rows = await self.db.fetch(
            "SELECT (ts + $1) / 86400 AS d, count(*) AS c FROM search_logs "
            "WHERE ts >= $2 GROUP BY d ORDER BY d", off, since,
        )
        return {r["d"]: r["c"] for r in rows}

    async def user_count(self, user_id: int) -> int:
        return await self.db.fetchval(
            "SELECT count(*) FROM search_logs WHERE user_id=$1", user_id
        ) or 0

    async def user_recent(self, user_id: int, limit: int = 15) -> list[Row]:
        return await self.db.fetch(
            "SELECT term, results, ts FROM search_logs WHERE user_id=$1 "
            "ORDER BY ts DESC, id DESC LIMIT $2", user_id, limit,
        )

    async def prune(self, older_than_days: int = 90) -> int:
        return await self.db.execute(
            "DELETE FROM search_logs WHERE ts < $1", timefmt.now() - older_than_days * 86400
        )

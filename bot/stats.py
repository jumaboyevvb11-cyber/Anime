"""Admin statistikasi: sahifalar uchun tayyor ma'lumotlar."""
from __future__ import annotations

from typing import Any

from bot.services.repo import Repo
from bot.utils import timefmt

DAY = 86400


class StatsService:
    def __init__(self, repo: Repo, storage: Any, access: Any, jikan: Any, db_label: str) -> None:
        self.repo, self.storage, self.access, self.jikan = repo, storage, access, jikan
        self.db_label = db_label

    async def overview(self) -> dict[str, Any]:
        r, now, today = self.repo, timefmt.now(), timefmt.day_start()
        return {
            "total": await r.users.total(),
            "new_today": await r.users.new_since(today),
            "new_week": await r.users.new_since(today - 6 * DAY),
            "active_24h": await r.users.active_since(now - DAY),
            "active_7d": await r.users.active_since(now - 7 * DAY),
            "active_30d": await r.users.active_since(now - 30 * DAY),
            "blocked": await r.users.blocked_count(),
            "bot_blocked": await r.users.bot_blocked_count(),
            "searches_total": await r.searches.total(),
            "searches_today": await r.searches.count_since(today),
            "searches_week": await r.searches.count_since(today - 6 * DAY),
        }

    async def users_page(self) -> dict[str, Any]:
        today = timefmt.day_start()
        since = today - 6 * DAY
        users = await self.repo.users.daily_new(since)
        searches = await self.repo.searches.daily(since)
        off = timefmt.tz_offset_seconds()
        days = []
        for n in range(7):
            start = since + n * DAY
            key = (start + off) // DAY
            days.append((timefmt.fmt_day(start), users.get(key, 0), searches.get(key, 0)))
        return {"days": days, "overview": await self.overview()}

    async def searches_page(self, period: str) -> dict[str, Any]:
        today = timefmt.day_start()
        since = {"d": today, "w": today - 6 * DAY, "m": today - 29 * DAY}.get(period, today)
        return {
            "since": since,
            "count": await self.repo.searches.count_since(since),
            "unique": await self.repo.searches.unique_users_since(since),
            "terms": await self.repo.searches.top_terms(since, 10),
            "total": await self.repo.searches.total(),
        }

    async def animes_page(self) -> list[dict[str, Any]]:
        return await self.repo.searches.top_animes(10)

    async def bot_page(self, started_at: float) -> dict[str, Any]:
        import platform
        import sys
        import time
        try:
            import aiogram
            aiogram_v = aiogram.__version__
        except Exception:  # noqa: BLE001
            aiogram_v = "?"
        return {
            "uptime": int(time.time() - started_at),
            "db": self.db_label,
            "favorites": await self.storage.total(),
            "custom_anime": self.repo.catalog.count(),
            "rec": len(self.repo.catalog.featured("rec")),
            "pop": len(self.repo.catalog.featured("pop")),
            "admins": len(self.access.admins()),
            "broadcasts": await self.repo.broadcasts.count(),
            "cache": len(getattr(self.jikan, "_cache", {})),
            "python": platform.python_version() if sys.version else "?",
            "aiogram": aiogram_v,
            "overview": await self.overview(),
        }

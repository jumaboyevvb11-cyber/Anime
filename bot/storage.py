"""Sevimli animelar saqlash: PostgreSQL (DATABASE_URL bor bo'lsa) yoki JSON fayl."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

Item = dict[str, Any]  # {"mal_id": int, "title": str, "score": float | None}


class BaseStorage:
    async def init(self) -> None: ...
    async def close(self) -> None: ...
    async def add(self, user_id: int, mal_id: int, title: str, score: float | None) -> None: ...
    async def remove(self, user_id: int, mal_id: int) -> None: ...
    async def exists(self, user_id: int, mal_id: int) -> bool: ...
    async def count(self, user_id: int) -> int: ...
    async def list(self, user_id: int, limit: int, offset: int) -> list[Item]: ...
    async def total(self) -> int: ...  # admin statistikasi uchun
    async def purge(self, mal_id: int) -> None: ...  # o'chirilgan anime hamma sevimlilardan olinadi


class PostgresStorage(BaseStorage):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool = None

    async def init(self) -> None:
        import asyncpg

        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        async with self.pool.acquire() as c:
            await c.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id    BIGINT NOT NULL,
                    mal_id     INTEGER NOT NULL,
                    title      TEXT NOT NULL,
                    score      REAL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (user_id, mal_id)
                )
                """
            )
        logger.info("PostgreSQL ulandi")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def add(self, user_id, mal_id, title, score) -> None:
        await self.pool.execute(
            "INSERT INTO favorites (user_id, mal_id, title, score) VALUES ($1,$2,$3,$4) "
            "ON CONFLICT DO NOTHING",
            user_id, mal_id, title, score,
        )

    async def remove(self, user_id, mal_id) -> None:
        await self.pool.execute(
            "DELETE FROM favorites WHERE user_id=$1 AND mal_id=$2", user_id, mal_id
        )

    async def exists(self, user_id, mal_id) -> bool:
        return bool(await self.pool.fetchval(
            "SELECT 1 FROM favorites WHERE user_id=$1 AND mal_id=$2", user_id, mal_id
        ))

    async def count(self, user_id) -> int:
        return await self.pool.fetchval(
            "SELECT count(*) FROM favorites WHERE user_id=$1", user_id
        )

    async def list(self, user_id, limit, offset) -> list[Item]:
        rows = await self.pool.fetch(
            "SELECT mal_id, title, score FROM favorites WHERE user_id=$1 "
            "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            user_id, limit, offset,
        )
        return [dict(r) for r in rows]

    async def total(self) -> int:
        return await self.pool.fetchval("SELECT count(*) FROM favorites") or 0

    async def purge(self, mal_id) -> None:
        await self.pool.execute("DELETE FROM favorites WHERE mal_id=$1", mal_id)


class JsonStorage(BaseStorage):
    """Oddiy fayl saqlash (lokal test uchun). Hostingda disk vaqtinchalik bo'lishi mumkin."""

    def __init__(self, path: str = "data/favorites.json") -> None:
        self.path = path
        self._data: dict[str, dict[str, Item]] = {}
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (OSError, ValueError):
                logger.exception("favorites.json o'qilmadi, bo'sh boshlandi")
        logger.warning("DATABASE_URL yo'q — sevimlilar JSON faylda saqlanadi")

    def _save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    async def add(self, user_id, mal_id, title, score) -> None:
        async with self._lock:
            self._data.setdefault(str(user_id), {})[str(mal_id)] = {
                "mal_id": mal_id, "title": title, "score": score, "ts": time.time(),
            }
            self._save()

    async def remove(self, user_id, mal_id) -> None:
        async with self._lock:
            self._data.get(str(user_id), {}).pop(str(mal_id), None)
            self._save()

    async def exists(self, user_id, mal_id) -> bool:
        return str(mal_id) in self._data.get(str(user_id), {})

    async def count(self, user_id) -> int:
        return len(self._data.get(str(user_id), {}))

    async def list(self, user_id, limit, offset) -> list[Item]:
        items = sorted(
            self._data.get(str(user_id), {}).values(), key=lambda i: i["ts"], reverse=True
        )
        return [
            {"mal_id": i["mal_id"], "title": i["title"], "score": i["score"]}
            for i in items[offset: offset + limit]
        ]

    async def total(self) -> int:
        return sum(len(v) for v in self._data.values())

    async def purge(self, mal_id) -> None:
        async with self._lock:
            for items in self._data.values():
                items.pop(str(mal_id), None)
            self._save()


def create_storage(database_url: str | None) -> BaseStorage:
    return PostgresStorage(database_url) if database_url else JsonStorage()

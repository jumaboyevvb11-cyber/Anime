"""Admin qo'shgan animelar va tavsiya/mashhur ro'yxatlari (xotirada keshlanadi)."""
from __future__ import annotations

from typing import Any

from bot.services.database import Database
from bot.utils import timefmt

Row = dict[str, Any]

EDITABLE = {"title", "title_en", "synopsis", "genres", "anime_type", "episodes",
            "year", "status", "score", "photo"}
KINDS = ("rec", "pop")  # tavsiya etilgan / mashhur


class CatalogRepo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.custom: dict[int, Row] = {}
        self._featured: dict[str, list[Row]] = {k: [] for k in KINDS}

    async def load(self) -> None:
        rows = await self.db.fetch("SELECT * FROM custom_anime ORDER BY id")
        self.custom = {r["id"]: r for r in rows}
        feat = await self.db.fetch("SELECT * FROM featured ORDER BY pos, added_at")
        self._featured = {k: [r for r in feat if r["kind"] == k] for k in KINDS}

    # ---------- admin qo'shgan animelar ----------
    def get(self, anime_id: int) -> Row | None:
        return self.custom.get(anime_id)

    def list_page(self, limit: int, offset: int) -> list[Row]:
        rows = sorted(self.custom.values(), key=lambda r: r["id"], reverse=True)
        return rows[offset: offset + limit]

    def count(self) -> int:
        return len(self.custom)

    def search_local(self, query: str, limit: int = 5) -> list[Row]:
        words = query.casefold().split()
        if not words:
            return []
        hits = []
        for r in self.custom.values():
            hay = f"{r['title']} {r.get('title_en') or ''}".casefold()
            if all(w in hay for w in words):
                hits.append(r)
        return sorted(hits, key=lambda r: r["id"], reverse=True)[:limit]

    async def add(self, values: Row, by: int | None) -> int:
        now = timefmt.now()
        new_id = await self.db.fetchval(
            "INSERT INTO custom_anime (title, title_en, synopsis, genres, anime_type, "
            "episodes, year, status, score, photo, created_by, created_at, updated_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$12) RETURNING id",
            values["title"], values.get("title_en"), values.get("synopsis"),
            values.get("genres"), values.get("anime_type"), values.get("episodes"),
            values.get("year"), values.get("status"), values.get("score"),
            values.get("photo"), by, now,
        )
        await self.load()
        return new_id

    async def update(self, anime_id: int, field: str, value: Any) -> bool:
        if field not in EDITABLE:
            raise ValueError(f"Noma'lum maydon: {field}")
        n = await self.db.execute(
            f"UPDATE custom_anime SET {field}=$2, updated_at=$3 WHERE id=$1",
            anime_id, value, timefmt.now(),
        )
        if n and field == "title":
            # tavsiya/mashhur ro'yxatlaridagi nom ham yangilansin
            await self.db.execute(
                "UPDATE featured SET title=$2 WHERE anime_id=$1", -anime_id, value)
        await self.load()
        return bool(n)

    async def delete(self, anime_id: int) -> bool:
        n = await self.db.execute("DELETE FROM custom_anime WHERE id=$1", anime_id)
        await self.db.execute("DELETE FROM featured WHERE anime_id=$1", -anime_id)
        await self.load()
        return bool(n)

    # ---------- tavsiya / mashhur ----------
    def featured(self, kind: str) -> list[Row]:
        return list(self._featured.get(kind, []))

    def is_featured(self, kind: str, anime_id: int) -> bool:
        return any(r["anime_id"] == anime_id for r in self._featured.get(kind, []))

    async def feature_add(self, kind: str, anime_id: int, title: str,
                          score: float | None, by: int | None) -> bool:
        if kind not in KINDS or self.is_featured(kind, anime_id):
            return False
        pos = max((r["pos"] for r in self._featured[kind]), default=0) + 1
        await self.db.execute(
            "INSERT INTO featured (kind, anime_id, title, score, pos, added_by, added_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (kind, anime_id) DO NOTHING",
            kind, anime_id, title[:200], score, pos, by, timefmt.now(),
        )
        await self.load()
        return True

    async def feature_remove(self, kind: str, anime_id: int) -> bool:
        n = await self.db.execute(
            "DELETE FROM featured WHERE kind=$1 AND anime_id=$2", kind, anime_id)
        await self.load()
        return bool(n)

    async def feature_move_up(self, kind: str, anime_id: int) -> bool:
        rows = self._featured.get(kind, [])
        idx = next((i for i, r in enumerate(rows) if r["anime_id"] == anime_id), None)
        if idx is None or idx == 0:
            return False
        a, b = rows[idx - 1], rows[idx]
        # joylarni almashtiramiz (pos qiymatlari takrorlanmasligi uchun tartib raqamlari qayta yoziladi)
        order = [r["anime_id"] for r in rows]
        order[idx - 1], order[idx] = order[idx], order[idx - 1]
        for n, aid in enumerate(order, start=1):
            await self.db.execute(
                "UPDATE featured SET pos=$3 WHERE kind=$1 AND anime_id=$2", kind, aid, n)
        await self.load()
        return True

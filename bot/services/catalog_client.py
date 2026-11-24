"""JikanClient kengaytmasi: admin qo'shgan animelar va tavsiya/mashhur ro'yxatlarini qo'shadi.

Mavjud handlerlar o'zgarmaydi: ular ``jikan`` obyektiga murojaat qilaveradi.
Admin qo'shgan animelar manfiy ID bilan (``-id``) ishlaydi, shuning uchun MAL ID lari bilan
to'qnashmaydi. Ular Jikan formatidagi lug'atga o'giriladi, shu sabab kartochka,
sevimlilar va klaviaturalar o'zgarishsiz ishlaydi.
"""
from __future__ import annotations

from typing import Any

from bot.services.jikan import PER_PAGE, JikanClient, JikanError, JikanNotFound
from bot.services.repo.catalog import CatalogRepo


def custom_to_jikan(row: dict[str, Any]) -> dict[str, Any]:
    genres = [g.strip() for g in (row.get("genres") or "").split(",") if g.strip()]
    data: dict[str, Any] = {
        "mal_id": -int(row["id"]),
        "_custom": True,
        "title": row["title"],
        "title_english": row.get("title_en") or None,
        "title_japanese": None,
        "synopsis": row.get("synopsis") or None,
        "score": row.get("score") or None,
        "scored_by": None, "rank": None, "popularity": None,
        "type": row.get("anime_type") or None,
        "episodes": row.get("episodes") or None,
        "status": row.get("status") or None,
        "aired": {"string": str(row["year"])} if row.get("year") else {},
        "duration": None, "studios": [],
        "genres": [{"name": g} for g in genres],
        "images": {"jpg": {"large_image_url": row["photo"]}} if row.get("photo") else {},
        "url": None, "rating": None,
    }
    return data


def snapshot_to_item(row: dict[str, Any]) -> dict[str, Any]:
    return {"mal_id": row["anime_id"], "title": row["title"], "score": row.get("score")}


class CatalogClient(JikanClient):
    def __init__(self, base_url: str, cache_ttl: int, catalog: CatalogRepo) -> None:
        super().__init__(base_url, cache_ttl)
        self.catalog = catalog

    async def search(self, query: str) -> list[dict[str, Any]]:
        local = [custom_to_jikan(r) for r in self.catalog.search_local(query)]
        try:
            remote = await super().search(query)
        except JikanError:
            if local:
                return local
            raise
        seen = {a["mal_id"] for a in local}
        return local + [a for a in remote if a["mal_id"] not in seen]

    async def anime(self, mal_id: int) -> dict[str, Any]:
        if mal_id < 0:
            row = self.catalog.get(-mal_id)
            if not row:
                raise JikanNotFound()
            return custom_to_jikan(row)
        return await super().anime(mal_id)

    async def similar(self, mal_id: int) -> list[dict[str, Any]]:
        if mal_id < 0:
            return []
        return await super().similar(mal_id)

    async def top(self, page: int = 1, popular: bool = False) -> tuple[list[dict], bool]:
        items, has_next = await super().top(page, popular)
        if popular and page == 1:
            pinned = [snapshot_to_item(r) for r in self.catalog.featured("pop")]
            if pinned:
                ids = {a["mal_id"] for a in pinned}
                items = pinned + [a for a in items if a["mal_id"] not in ids]
        return items, has_next

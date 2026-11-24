"""Jikan API (MyAnimeList) uchun asinxron klient: kesh, rate-limit, qayta urinish."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

HIDDEN_GENRES = {"Hentai", "Erotica"}
PER_PAGE = 10


class JikanError(Exception):
    user_message = "⚠️ Xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."


class JikanNotFound(JikanError):
    user_message = "😕 Anime topilmadi."


class JikanUnavailable(JikanError):
    user_message = (
        "⏳ Anime serveri hozir band yoki javob bermayapti.\n"
        "Iltimos, bir necha soniyadan keyin qayta urinib ko'ring."
    )


def is_safe(anime: dict[str, Any]) -> bool:
    if (anime.get("rating") or "").startswith("Rx"):
        return False
    names = {g.get("name") for g in anime.get("genres") or []}
    return not (names & HIDDEN_GENRES)


class JikanClient:
    def __init__(self, base_url: str, cache_ttl: int = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_ttl = cache_ttl
        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0
        self._min_interval = 0.4  # Jikan: sekundiga 3 ta so'rov

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "AnimeTelegramBot/1.0"},
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    # ---------- ichki yordamchilar ----------
    async def _throttle(self) -> None:
        async with self._rate_lock:
            wait = self._min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    def _cache_get(self, key: str) -> Any | None:
        hit = self._cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        self._cache.pop(key, None)
        return None

    def _cache_set(self, key: str, value: Any, ttl: int) -> None:
        if len(self._cache) > 500:
            now = time.monotonic()
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
            if len(self._cache) > 500:
                self._cache.clear()
        self._cache[key] = (time.monotonic() + ttl, value)

    async def _get(
        self, path: str, params: dict[str, Any] | None = None, ttl: int | None = None
    ) -> dict[str, Any]:
        assert self._session is not None, "JikanClient.start() chaqirilmagan"
        params = {k: str(v) for k, v in (params or {}).items() if v is not None}
        ttl = self.cache_ttl if ttl is None else ttl
        key = f"{path}?{urlencode(sorted(params.items()))}"
        if ttl > 0 and (cached := self._cache_get(key)) is not None:
            return cached

        for attempt in range(1, 4):
            await self._throttle()
            try:
                async with self._session.get(self.base_url + path, params=params) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        if ttl > 0:
                            self._cache_set(key, data, ttl)
                        return data
                    if r.status == 404:
                        raise JikanNotFound()
                    if r.status == 429 or r.status >= 500:
                        logger.warning("Jikan %s -> %s (urinish %s)", path, r.status, attempt)
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    logger.error("Jikan %s -> kutilmagan status %s", path, r.status)
                    raise JikanError()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("Jikan tarmoq xatosi (%s): %s", attempt, exc)
                await asyncio.sleep(attempt)
        raise JikanUnavailable()

    # ---------- ochiq metodlar ----------
    async def search(self, query: str) -> list[dict[str, Any]]:
        data = await self._get(
            "/anime",
            {"q": query, "limit": PER_PAGE, "sfw": "true",
             "order_by": "members", "sort": "desc"},
        )
        return [a for a in data.get("data", []) if is_safe(a)]

    async def top(self, page: int = 1, popular: bool = False) -> tuple[list[dict], bool]:
        data = await self._get(
            "/top/anime",
            {"page": page, "limit": PER_PAGE, "sfw": "true",
             "filter": "bypopularity" if popular else None},
        )
        items = [a for a in data.get("data", []) if is_safe(a)]
        return items, bool(data.get("pagination", {}).get("has_next_page"))

    async def genres(self) -> list[dict[str, Any]]:
        data = await self._get("/genres/anime", {"filter": "genres"}, ttl=86400)
        return [g for g in data.get("data", []) if g.get("name") not in HIDDEN_GENRES]

    async def genre_name(self, genre_id: int) -> str:
        for g in await self.genres():
            if g["mal_id"] == genre_id:
                return g["name"]
        return "Janr"

    async def by_genre(self, genre_id: int, page: int = 1) -> tuple[list[dict], bool]:
        data = await self._get(
            "/anime",
            {"genres": genre_id, "page": page, "limit": PER_PAGE, "sfw": "true",
             "order_by": "score", "sort": "desc", "min_score": 6},
        )
        items = [a for a in data.get("data", []) if is_safe(a)]
        return items, bool(data.get("pagination", {}).get("has_next_page"))

    async def anime(self, mal_id: int) -> dict[str, Any]:
        data = (await self._get(f"/anime/{mal_id}")).get("data")
        if not data or not is_safe(data):
            raise JikanNotFound()
        return data

    async def similar(self, mal_id: int) -> list[dict[str, Any]]:
        data = await self._get(f"/anime/{mal_id}/recommendations", ttl=3600)
        return [r["entry"] for r in data.get("data", [])[:PER_PAGE] if r.get("entry")]

    async def random(self) -> dict[str, Any]:
        for _ in range(4):
            data = (await self._get("/random/anime", ttl=0)).get("data")
            if data and is_safe(data):
                return data
        raise JikanUnavailable()

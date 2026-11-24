"""Admin paneli ma'lumotlar qatlami: barcha repozitoriyalar bitta ``Repo`` da."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

from bot.services.database import Database

from .admins import AdminsRepo, LogsRepo
from .broadcasts import BroadcastsRepo
from .catalog import CatalogRepo
from .searches import SearchesRepo
from .users import UsersRepo

logger = logging.getLogger(__name__)

__all__ = ["Repo"]


class Repo:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UsersRepo(db)
        self.searches = SearchesRepo(db)
        self.catalog = CatalogRepo(db)
        self.admins = AdminsRepo(db)
        self.logs = LogsRepo(db)
        self.broadcasts = BroadcastsRepo(db)
        self._tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        await self.db.start()
        await self.users.load()
        await self.catalog.load()
        interrupted = await self.broadcasts.mark_interrupted()
        if interrupted:
            logger.warning("Oldingi sessiyada to'xtab qolgan %s ta xabar yuborish belgilandi", interrupted)
        await self.searches.prune(90)

    async def close(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        await self.db.close()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        """Orqa fonda bajarish: handler kutib qolmaydi, xato botni to'xtatmaydi."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception():
                logger.warning("Orqa fon vazifasi xatosi: %s", t.exception())

        task.add_done_callback(_done)

    def track_search(self, user_id: int, term: str, results: int) -> None:
        self.spawn(self.searches.log(user_id, term, results))

    def track_view(self, anime: dict[str, Any]) -> None:
        title = anime.get("title_english") or anime.get("title") or "?"
        self.spawn(self.searches.track_view(anime["mal_id"], title))

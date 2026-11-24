"""Foydalanuvchilarni kuzatish va bloklanganlarni to'xtatish (tezkor: baza so'rovlari orqa fonda)."""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.services.access import AccessService
from bot.services.repo import Repo

logger = logging.getLogger(__name__)

BLOCKED_TEXT = "🚫 Siz botdan foydalanishdan bloklangansiz."


class UserTrackingMiddleware(BaseMiddleware):
    TOUCH_INTERVAL = 60  # soniya: bir foydalanuvchi uchun bazaga yozish chastotasi

    def __init__(self, repo: Repo, access: AccessService) -> None:
        self.repo = repo
        self.access = access
        self._seen: dict[int, float] = {}

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if user is not None and not user.is_bot:
            if user.id in self.repo.users.blocked and not self.access.is_admin(user.id):
                await self._reject(event)
                return None
            chat = event.chat if isinstance(event, Message) else getattr(
                getattr(event, "message", None), "chat", None)
            if chat is None or chat.type == "private":
                self._touch(user)
        return await handler(event, data)

    def _touch(self, user: Any) -> None:
        now = time.monotonic()
        last = self._seen.get(user.id)
        if last is not None and now - last < self.TOUCH_INTERVAL:
            return
        if len(self._seen) > 200_000:
            self._seen.clear()
        self._seen[user.id] = now
        self.repo.spawn(self.repo.users.upsert(user.id, user.full_name or "", user.username))
        if self.access.is_admin(user.id):
            self.repo.spawn(self.access.sync_profile(user.id, user.full_name or "", user.username))

    @staticmethod
    async def _reject(event: TelegramObject) -> None:
        try:
            if isinstance(event, CallbackQuery):
                await event.answer(BLOCKED_TEXT, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(BLOCKED_TEXT)
        except Exception:  # noqa: BLE001
            logger.debug("Bloklangan foydalanuvchiga javob yuborib bo'lmadi")

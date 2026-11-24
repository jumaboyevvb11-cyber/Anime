"""Admin handlerlari uchun umumiy yordamchilar: ruxsat tekshiruvi, filtrlar, yordamchi funksiyalar."""
from __future__ import annotations

import logging
from math import ceil
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from bot.services.access import AccessService, AdminInfo
from bot.services.repo import Repo
from bot.keyboards_admin import UNKNOWN
from bot.utils.messages import edit_or_send
from bot.utils.text import esc

logger = logging.getLogger(__name__)

PER_PAGE = 8

ACTION_LABELS = {
    "super_claim": "👑 Super Admin bog'landi",
    "user_block": "🚫 Foydalanuvchi bloklandi",
    "user_unblock": "✅ Blokdan chiqarildi",
    "broadcast_start": "📣 Xabar yuborish boshlandi",
    "broadcast_stop": "⏹ Xabar yuborish to'xtatildi",
    "broadcast_end": "📬 Xabar yuborish tugadi",
    "anime_add": "➕ Anime qo'shildi",
    "anime_edit": "✏️ Anime tahrirlandi",
    "anime_delete": "🗑 Anime o'chirildi",
    "feature_add": "⭐ Ro'yxatga qo'shildi",
    "feature_remove": "➖ Ro'yxatdan olindi",
    "feature_move": "⬆️ Ro'yxat tartibi o'zgardi",
    "admin_add": "🛡 Admin qo'shildi",
    "admin_perms": "🔧 Admin huquqlari o'zgardi",
    "admin_remove": "🗑 Admin olib tashlandi",
}


def pages_for(total: int, per: int = PER_PAGE) -> int:
    return max(1, ceil(total / per))


def clamp_page(page: int, pages: int) -> int:
    return min(max(page, 1), pages)


def user_display(u: Any) -> str:
    return getattr(u, "full_name", None) or getattr(u, "first_name", None) or UNKNOWN


def mention(name: str, uid: int, username: str | None = None) -> str:
    uname = f" (@{esc(username)})" if username else ""
    return f"<b>{esc(name or UNKNOWN)}</b>{uname} · <code>{uid}</code>"


class AdminGuard(BaseMiddleware):
    """Ichki middleware: handler tanlangandan keyin ishlaydi, shuning uchun oddiy
    foydalanuvchilar xabarlari (qidiruv) bu yerga umuman kelmaydi. Admin amaliga
    tegishli har bir handler chaqiruvidan oldin ID va huquq tekshiriladi."""

    def __init__(self, perm: str | None = None) -> None:
        self.perm = perm

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        access: AccessService = data["access"]
        user = getattr(event, "from_user", None)
        admin = access.get(user.id) if user else None
        chat = event.chat if isinstance(event, Message) else getattr(
            getattr(event, "message", None), "chat", None)
        private = chat is None or chat.type == "private"
        allowed = admin is not None and private and (self.perm is None or admin.can(self.perm))
        if not allowed:
            logger.warning("Admin amali rad etildi: user=%s perm=%s", getattr(user, "id", None), self.perm)
            text = ("⛔ Bu amal uchun ruxsatingiz yo'q." if admin or not private
                    else "⛔ Bu bo'lim faqat adminlar uchun.")
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
            return None
        data["admin"] = admin
        return await handler(event, data)


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject, access: AccessService) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and access.is_admin(user.id))


def guard_router(router, perm: str | None) -> None:
    router.message.middleware(AdminGuard(perm))
    router.callback_query.middleware(AdminGuard(perm))


async def show(event: Message | CallbackQuery, text: str,
               markup: InlineKeyboardMarkup | None = None) -> None:
    """Callback bo'lsa xabarni tahrirlaydi, aks holda yangi xabar yuboradi."""
    if isinstance(event, CallbackQuery):
        await edit_or_send(event, text, markup)
    else:
        await event.answer(text, reply_markup=markup)


async def log_action(repo: Repo, admin: AdminInfo, action: str, details: str = "") -> None:
    try:
        await repo.logs.add(admin.user_id, admin.name, action, details)
    except Exception:  # noqa: BLE001 — tarix yozilmasa ham amal bekor bo'lmasin
        logger.exception("Admin harakatini yozib bo'lmadi")


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except Exception:  # noqa: BLE001
        return False

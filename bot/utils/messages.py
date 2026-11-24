"""Xabar yuborish yordamchilari."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.keyboards import anime_detail
from bot.services.storage import BaseStorage
from bot.utils.text import build_caption, get_image

logger = logging.getLogger(__name__)


async def send_anime(
    bot: Bot, chat_id: int, user_id: int, anime: dict[str, Any], storage: BaseStorage
) -> None:
    kb = anime_detail(anime, await storage.exists(user_id, anime["mal_id"]))
    caption = build_caption(anime)
    if image := get_image(anime):
        try:
            await bot.send_photo(chat_id, image, caption=caption, reply_markup=kb)
            return
        except TelegramBadRequest as exc:
            logger.warning("Rasm yuborilmadi (%s), matn yuboriladi", exc)
    await bot.send_message(chat_id, caption, reply_markup=kb)


async def edit_or_send(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None) -> None:
    """Matnli xabarni tahrirlaydi; rasm/yopilgan xabar bo'lsa yangisini yuboradi."""
    msg = cb.message
    if isinstance(msg, Message) and not msg.photo:
        try:
            await msg.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc):
                return
    if isinstance(msg, Message):
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=kb)

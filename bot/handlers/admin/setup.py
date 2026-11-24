"""Hamma uchun ochiq buyruqlar: /id va Super Admin ni xavfsiz bog'lash (/claim)."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.keyboards import main_menu
from bot.services.access import AccessService, ClaimResult

router = Router(name="admin_setup")
logger = logging.getLogger(__name__)

GENERIC_FAIL = "❌ Kod yoki foydalanuvchi mos kelmadi."


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("claim"))
async def cmd_claim(message: Message, command: CommandObject, access: AccessService) -> None:
    """Super Admin ni ID bilan bog'lash. Faqat shaxsiy chatda va faqat bog'lanmagan bo'lsa ishlaydi."""
    if message.chat.type != "private" or not message.from_user:
        return
    if not access.claim_enabled:
        return  # bog'langan bo'lsa buyruq mavjud emasdek jim turadi
    code = (command.args or "").strip()
    try:  # kod chatda qolib ketmasin
        await message.delete()
    except Exception:  # noqa: BLE001
        pass
    if not code:
        await message.bot.send_message(message.chat.id, "ℹ️ Format: <code>/claim KOD</code>")
        return
    u = message.from_user
    res = await access.try_claim(u.id, u.username, u.full_name, code)
    if res == ClaimResult.OK:
        await message.bot.send_message(
            message.chat.id,
            f"✅ Siz <b>Super Admin</b> sifatida bog'landingiz.\n🆔 ID: <code>{u.id}</code>\n\n"
            "Endi tekshiruv Telegram ID bo'yicha amalga oshadi. /admin — panelni ochish.",
            reply_markup=main_menu(is_admin=True),
        )
    elif res == ClaimResult.LOCKED:
        await message.bot.send_message(message.chat.id, "⏳ Juda ko'p urinish. Keyinroq qayta urinib ko'ring.")
    elif res == ClaimResult.WRONG:
        await message.bot.send_message(message.chat.id, GENERIC_FAIL)

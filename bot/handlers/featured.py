"""Foydalanuvchi uchun: admin tanlagan «Tavsiya etilgan animelar» ro'yxati."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.callbacks import CB_FEATURED
from bot.keyboards import anime_list
from bot.services.catalog_client import snapshot_to_item
from bot.services.repo import Repo

router = Router(name="featured")


@router.callback_query(F.data == CB_FEATURED)
async def featured_list(cb: CallbackQuery, repo: Repo) -> None:
    rows = repo.catalog.featured("rec")
    if not rows:
        await cb.answer("Hozircha admin tavsiyalari yo'q.", show_alert=True)
        return
    await cb.answer()
    await cb.bot.send_message(
        cb.from_user.id, "⭐ <b>Admin tavsiyalari</b>\n👇 Birini tanlang:",
        reply_markup=anime_list([snapshot_to_item(r) for r in rows]),
    )

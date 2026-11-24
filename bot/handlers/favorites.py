"""Sevimli animelar."""
from math import ceil

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.callbacks import FavCB, PageCB
from bot.keyboards import BTN_FAVORITES, anime_detail, anime_list, pagination_row
from bot.services.jikan import JikanClient
from bot.services.storage import BaseStorage
from bot.utils.messages import edit_or_send

router = Router(name="favorites")

PER_PAGE = 8
EMPTY = ("⭐ <b>Sevimlilar</b>\n\nHozircha bo'sh.\n"
         "Anime sahifasidagi «⭐ Sevimlilarga qo'shish» tugmasini bosing.")


async def render_favs(user_id: int, page: int, storage: BaseStorage
                      ) -> tuple[str, InlineKeyboardMarkup | None]:
    total = await storage.count(user_id)
    if not total:
        return EMPTY, None
    pages = ceil(total / PER_PAGE)
    page = min(max(page, 1), pages)
    offset = (page - 1) * PER_PAGE
    items = await storage.list(user_id, PER_PAGE, offset)
    kb = anime_list(items, start=offset + 1, nav=pagination_row("fav", page, page < pages))
    return f"⭐ <b>Sevimli animelaringiz</b> ({total} ta)", kb


@router.message(Command("favorites"))
@router.message(F.text == BTN_FAVORITES)
async def favorites_msg(message: Message, storage: BaseStorage) -> None:
    text, kb = await render_favs(message.from_user.id, 1, storage)
    await message.answer(text, reply_markup=kb)


@router.callback_query(PageCB.filter(F.kind == "fav"))
async def favorites_page(cb: CallbackQuery, callback_data: PageCB,
                         storage: BaseStorage) -> None:
    await cb.answer()
    text, kb = await render_favs(cb.from_user.id, callback_data.page, storage)
    await edit_or_send(cb, text, kb)


@router.callback_query(FavCB.filter())
async def toggle_favorite(cb: CallbackQuery, callback_data: FavCB,
                          jikan: JikanClient, storage: BaseStorage) -> None:
    anime = await jikan.anime(callback_data.id)
    uid = cb.from_user.id
    adding = callback_data.act == "add"
    if adding:
        await storage.add(uid, anime["mal_id"], anime.get("title_english") or anime["title"],
                          anime.get("score"))
        await cb.answer("⭐ Sevimlilarga qo'shildi")
    else:
        await storage.remove(uid, anime["mal_id"])
        await cb.answer("💔 Sevimlilardan olib tashlandi")
    try:
        await cb.message.edit_reply_markup(reply_markup=anime_detail(anime, adding))
    except TelegramBadRequest:
        pass

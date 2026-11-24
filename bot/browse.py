"""Top, mashhur va janrlar bo'limlari."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.callbacks import CB_GENRES, CB_NOOP, PageCB
from bot.keyboards import (BTN_GENRES, BTN_POPULAR, BTN_TOP, anime_list,
                           genres_back, genres_kb, pagination_row)
from bot.services.jikan import PER_PAGE, JikanClient
from bot.utils.messages import edit_or_send
from bot.utils.text import esc, genre_uz

router = Router(name="browse")

GENRES_TEXT = "🎭 <b>Janrni tanlang:</b>"


async def render_page(
    kind: str, page: int, arg: int, jikan: JikanClient
) -> tuple[str, InlineKeyboardMarkup]:
    footer = None
    if kind == "top":
        items, has_next = await jikan.top(page)
        title = "🏆 <b>Top anime reytingi</b>"
    elif kind == "pop":
        items, has_next = await jikan.top(page, popular=True)
        title = "🔥 <b>Mashhur animelar</b>"
    else:
        items, has_next = await jikan.by_genre(arg, page)
        title = f"🎭 <b>{esc(genre_uz(await jikan.genre_name(arg)))}</b> janri"
        footer = genres_back()
    if not items:
        return f"{title}\n\n😕 Natija topilmadi.", anime_list([], footer=footer)
    kb = anime_list(
        items, start=(page - 1) * PER_PAGE + 1,
        nav=pagination_row(kind, page, has_next, arg), footer=footer,
    )
    return f"{title}\n👇 Birini tanlang:", kb


@router.message(Command("top"))
@router.message(F.text == BTN_TOP)
async def top_msg(message: Message, jikan: JikanClient) -> None:
    text, kb = await render_page("top", 1, 0, jikan)
    await message.answer(text, reply_markup=kb)


@router.message(Command("popular"))
@router.message(F.text == BTN_POPULAR)
async def popular_msg(message: Message, jikan: JikanClient) -> None:
    text, kb = await render_page("pop", 1, 0, jikan)
    await message.answer(text, reply_markup=kb)


@router.message(Command("genres"))
@router.message(F.text == BTN_GENRES)
async def genres_msg(message: Message, jikan: JikanClient) -> None:
    await message.answer(GENRES_TEXT, reply_markup=genres_kb(await jikan.genres()))


@router.callback_query(F.data == CB_GENRES)
async def genres_cb(cb: CallbackQuery, jikan: JikanClient) -> None:
    await cb.answer()
    await edit_or_send(cb, GENRES_TEXT, genres_kb(await jikan.genres()))


@router.callback_query(PageCB.filter(F.kind.in_({"top", "pop", "genre"})))
async def page_cb(cb: CallbackQuery, callback_data: PageCB, jikan: JikanClient) -> None:
    await cb.answer()
    text, kb = await render_page(callback_data.kind, callback_data.page,
                                 callback_data.arg, jikan)
    await edit_or_send(cb, text, kb)


@router.callback_query(F.data == CB_NOOP)
async def noop(cb: CallbackQuery) -> None:
    await cb.answer()

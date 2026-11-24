"""Barcha klaviaturalar."""
from __future__ import annotations

from typing import Any

from aiogram.types import (InlineKeyboardButton as Btn, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

from bot.callbacks import (CB_FEATURED, CB_GENRES, CB_NOOP, CB_RANDOM, CB_REC_FAV,
                           AnimeCB, FavCB, PageCB, SimCB)
from bot.utils.text import button_label, genre_uz

BTN_SEARCH = "🔍 Qidirish"
BTN_POPULAR = "🔥 Mashhur"
BTN_TOP = "🏆 Top reyting"
BTN_GENRES = "🎭 Janrlar"
BTN_RECOMMEND = "🎲 Tavsiya"
BTN_FAVORITES = "⭐ Sevimlilar"
BTN_HELP = "ℹ️ Yordam"
BTN_ADMIN = "🛠 Admin panel"  # faqat adminlarga ko'rinadi


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    k = KeyboardButton
    rows = [
        [k(text=BTN_SEARCH), k(text=BTN_POPULAR)],
        [k(text=BTN_TOP), k(text=BTN_GENRES)],
        [k(text=BTN_RECOMMEND), k(text=BTN_FAVORITES)],
        [k(text=BTN_HELP)],
    ]
    if is_admin:
        rows.append([k(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Anime nomini yozing...",
    )


def pagination_row(kind: str, page: int, has_next: bool, arg: int = 0) -> list[Btn]:
    row: list[Btn] = []
    if page > 1:
        row.append(Btn(text="◀️ Oldingi",
                       callback_data=PageCB(kind=kind, page=page - 1, arg=arg).pack()))
    row.append(Btn(text=f"📄 {page}", callback_data=CB_NOOP))
    if has_next:
        row.append(Btn(text="Keyingi ▶️",
                       callback_data=PageCB(kind=kind, page=page + 1, arg=arg).pack()))
    return row


def anime_list(
    items: list[dict[str, Any]],
    start: int | None = None,
    nav: list[Btn] | None = None,
    footer: list[list[Btn]] | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [Btn(text=button_label(a, start + i if start else None),
             callback_data=AnimeCB(id=a["mal_id"]).pack())]
        for i, a in enumerate(items)
    ]
    if nav:
        rows.append(nav)
    rows.extend(footer or [])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def genres_kb(genres: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = [
        Btn(text=genre_uz(g["name"]),
            callback_data=PageCB(kind="genre", page=1, arg=g["mal_id"]).pack())
        for g in genres
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def genres_back() -> list[list[Btn]]:
    return [[Btn(text="🎭 Janrlar", callback_data=CB_GENRES)]]


def recommend_menu(has_featured: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [Btn(text="🎲 Tasodifiy anime", callback_data=CB_RANDOM)],
        [Btn(text="🎯 Sevimlilarimga o'xshash", callback_data=CB_REC_FAV)],
        [Btn(text="🎭 Janr bo'yicha", callback_data=CB_GENRES)],
    ]
    if has_featured:
        rows.insert(0, [Btn(text="⭐ Admin tavsiyalari", callback_data=CB_FEATURED)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def anime_detail(anime: dict[str, Any], is_fav: bool) -> InlineKeyboardMarkup:
    mal_id = anime["mal_id"]
    fav = Btn(
        text="💔 Sevimlilardan olib tashlash" if is_fav else "⭐ Sevimlilarga qo'shish",
        callback_data=FavCB(id=mal_id, act="del" if is_fav else "add").pack(),
    )
    row2 = [Btn(text="🔁 O'xshash", callback_data=SimCB(id=mal_id).pack())]
    if anime.get("url"):
        row2.append(Btn(text="🔗 MyAnimeList", url=anime["url"]))
    return InlineKeyboardMarkup(inline_keyboard=[
        [fav], row2, [Btn(text="🎲 Tasodifiy anime", callback_data=CB_RANDOM)],
    ])

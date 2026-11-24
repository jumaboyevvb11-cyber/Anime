"""⭐ Tavsiya etilgan va 🔥 mashhur animelar ro'yxatlarini boshqarish."""
from __future__ import annotations

import re
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import b, fa_list, fa_results, kb
from bot.services.access import AdminInfo
from bot.services.jikan import JikanClient, JikanError
from bot.services.repo import Repo
from bot.states import FeaturedSG
from bot.utils.text import esc

from .common import guard_router, log_action, show

router = Router(name="admin_featured")
guard_router(router, "anime")

KIND_TITLES = {"rec": "⭐ Tavsiya etilgan animelar", "pop": "🔥 Mashhur animelar ro'yxati"}
KIND_NAMES = {"rec": "Tavsiya", "pop": "Mashhur"}
KIND_HELP = {
    "rec": "Foydalanuvchilar «🎲 Tavsiya» bo'limida «⭐ Admin tavsiyalari» tugmasi orqali ko'radi.",
    "pop": "«🔥 Mashhur» bo'limida ro'yxatning eng tepasida chiqadi (MyAnimeList natijalaridan oldin).",
}
ID_RE = re.compile(r"(?:anime/)?(\d{1,7})\b")


def list_text(kind: str, items: list[dict[str, Any]]) -> str:
    text = f"<b>{KIND_TITLES[kind]}</b> — {len(items)} ta\n<i>{KIND_HELP[kind]}</i>"
    if not items:
        text += "\n\n😕 Ro'yxat bo'sh. «➕ Qo'shish» tugmasini bosing."
    else:
        text += "\n\n⬆️ — yuqoriga ko'tarish · 🗑 — olib tashlash"
    return text


async def show_list(event: Message | CallbackQuery, kind: str, repo: Repo) -> None:
    items = repo.catalog.featured(kind)
    await show(event, list_text(kind, items), fa_list(kind, items))


async def add_item(kind: str, anime: dict[str, Any], repo: Repo, admin: AdminInfo) -> bool:
    title = anime.get("title_english") or anime.get("title") or "?"
    ok = await repo.catalog.feature_add(kind, anime["mal_id"], title, anime.get("score"), admin.user_id)
    if ok:
        await log_action(repo, admin, "feature_add", f"{KIND_NAMES[kind]}: {title}")
    return ok


@router.callback_query(AdmCB.filter((F.sec == "fa") & (F.act == "list")))
async def fa_home(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, state: FSMContext) -> None:
    if callback_data.arg not in KIND_TITLES:
        await cb.answer("Noma'lum ro'yxat", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await show_list(cb, callback_data.arg, repo)


@router.callback_query(AdmCB.filter((F.sec == "fa") & (F.act == "add")))
async def fa_add(cb: CallbackQuery, callback_data: AdmCB, state: FSMContext) -> None:
    if callback_data.arg not in KIND_TITLES:
        await cb.answer("Noma'lum ro'yxat", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(FeaturedSG.query)
    await state.update_data(kind=callback_data.arg)
    await show(cb, f"➕ <b>{KIND_TITLES[callback_data.arg]}</b>\n\nAnime <b>nomini</b> yoki MyAnimeList "
                   "<b>ID / havolasini</b> yuboring.\nMasalan: <code>Naruto</code> yoki "
                   "<code>https://myanimelist.net/anime/20</code>\n\nBekor qilish: /cancel",
               kb([_cancel(callback_data.arg)]))


def _cancel(kind: str):
    return b("❌ Bekor qilish", "fa", "list", arg=kind)


@router.message(FeaturedSG.query, F.text, ~F.text.startswith("/"))
async def fa_query(message: Message, state: FSMContext, repo: Repo, jikan: JikanClient,
                   admin: AdminInfo) -> None:
    kind = (await state.get_data()).get("kind")
    if kind not in KIND_TITLES:
        await message.answer("Sessiya tugagan. /admin")
        return
    text = message.text.strip()
    if "myanimelist.net" in text or text.isdigit():
        m = ID_RE.search(text)
        if not m:
            await message.answer("⚠️ ID topilmadi. Raqam yoki havola yuboring.")
            return
        try:
            anime = await jikan.anime(int(m.group(1)))
        except JikanError as exc:
            await message.answer(exc.user_message)
            return
        await state.clear()
        ok = await add_item(kind, anime, repo, admin)
        await message.answer("✅ Qo'shildi." if ok else "ℹ️ Bu anime ro'yxatda allaqachon bor.")
        await show_list(message, kind, repo)
        return
    if len(text) < 2:
        await message.answer("✏️ Kamida 2 ta belgi kiriting.")
        return
    try:
        items = await jikan.search(text[:100])
    except JikanError as exc:
        await message.answer(exc.user_message)
        return
    if not items:
        await message.answer(f"😕 «{esc(text)}» bo'yicha topilmadi. Boshqa nom yuboring yoki /cancel.")
        return
    await message.answer("🔍 Natijalar. Qo'shish uchun birini tanlang:", reply_markup=fa_results(kind, items))


@router.message(FeaturedSG.query)
async def fa_wrong(message: Message) -> None:
    await message.answer("✏️ Anime nomi yoki ID ni matn ko'rinishida yuboring (yoki /cancel).")


@router.callback_query(AdmCB.filter((F.sec == "fa") & (F.act == "pick")))
async def fa_pick(cb: CallbackQuery, callback_data: AdmCB, state: FSMContext, repo: Repo,
                  jikan: JikanClient, admin: AdminInfo) -> None:
    kind = callback_data.arg
    if kind not in KIND_TITLES:
        await cb.answer("Noma'lum ro'yxat", show_alert=True)
        return
    try:
        anime = await jikan.anime(callback_data.id)
    except JikanError as exc:
        await cb.answer(re.sub(r"<[^>]+>", "", exc.user_message)[:190], show_alert=True)
        return
    await state.clear()
    ok = await add_item(kind, anime, repo, admin)
    await cb.answer("✅ Qo'shildi" if ok else "ℹ️ Allaqachon ro'yxatda bor")
    await show_list(cb, kind, repo)


@router.callback_query(AdmCB.filter((F.sec == "fa") & (F.act == "up")))
async def fa_up(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, admin: AdminInfo) -> None:
    kind = callback_data.arg
    if kind not in KIND_TITLES or not await repo.catalog.feature_move_up(kind, callback_data.id):
        await cb.answer("Ko'tarib bo'lmadi", show_alert=True)
        return
    await log_action(repo, admin, "feature_move", f"{KIND_NAMES[kind]}: ID {callback_data.id}")
    await cb.answer("⬆️ Ko'tarildi")
    await show_list(cb, kind, repo)


@router.callback_query(AdmCB.filter((F.sec == "fa") & (F.act == "rm")))
async def fa_remove(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, admin: AdminInfo) -> None:
    kind = callback_data.arg
    row = next((r for r in repo.catalog.featured(kind) if r["anime_id"] == callback_data.id), None)
    if kind not in KIND_TITLES or not row or not await repo.catalog.feature_remove(kind, callback_data.id):
        await cb.answer("Topilmadi", show_alert=True)
        return
    await log_action(repo, admin, "feature_remove", f"{KIND_NAMES[kind]}: {row['title']}")
    await cb.answer("🗑 Olib tashlandi")
    await show_list(cb, kind, repo)

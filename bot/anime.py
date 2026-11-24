"""🎬 Anime boshqaruvi: qo'shish, tahrirlash, o'chirish (admin qo'shgan animelar)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import (an_card, an_list, an_menu, back_row, confirm_kb, form_confirm,
                                 form_kb, kb)
from bot.services.access import AdminInfo
from bot.services.catalog_client import custom_to_jikan
from bot.services.repo import Repo
from bot.services.storage import BaseStorage
from bot.states import AnimeFormSG
from bot.utils.text import build_caption, esc, get_image

from .common import PER_PAGE, clamp_page, guard_router, log_action, pages_for, show

router = Router(name="admin_anime")
guard_router(router, "anime")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Field:
    key: str
    title: str
    prompt: str
    kind: str  # text | genres | int | float | choice | photo
    required: bool = False
    choices: tuple[tuple[str, str], ...] = ()
    lo: float = 0
    hi: float = 0
    max_len: int = 120


FIELDS: tuple[Field, ...] = (
    Field("title", "Nomi", "Anime nomini yuboring.\nMasalan: <code>Mening animem</code>", "text", True),
    Field("title_en", "Inglizcha nom", "Inglizcha nomini yuboring.", "text"),
    Field("synopsis", "Tavsif", "Qisqacha mazmunini yuboring (maks. 800 belgi).", "text", max_len=800),
    Field("genres", "Janrlar", "Janrlarni vergul bilan yuboring.\nMasalan: <code>Jangari, Drama, Sarguzasht</code>", "genres"),
    Field("anime_type", "Turi", "Turini tanlang:", "choice", choices=(
        ("TV", "📺 TV serial"), ("Movie", "🎞 Film"), ("OVA", "OVA"), ("ONA", "ONA"), ("Special", "Maxsus"))),
    Field("episodes", "Qismlar soni", "Qismlar sonini yuboring (1–5000).", "int", lo=1, hi=5000),
    Field("year", "Chiqqan yili", "Chiqqan yilini yuboring. Masalan: <code>2021</code>", "int",
          lo=1950, hi=datetime.now().year + 5),
    Field("status", "Holati", "Holatini tanlang:", "choice", choices=(
        ("Finished Airing", "✅ Tugagan"), ("Currently Airing", "📡 Efirda"),
        ("Not yet aired", "🕐 Hali chiqmagan"))),
    Field("score", "Reyting", "Reytingni yuboring (0 dan 10 gacha). Masalan: <code>8.5</code>", "float", lo=0, hi=10),
    Field("photo", "Rasm", "Poster rasmini yuboring (rasm sifatida).", "photo"),
)
BY_KEY = {f.key: f for f in FIELDS}
STATUS_LABEL = {v: label for v, label in BY_KEY["status"].choices}
TYPE_LABEL = {v: label for v, label in BY_KEY["anime_type"].choices}


def parse_value(field: Field, text: str) -> Any:
    text = text.strip()
    if field.kind == "text":
        if field.required and len(text) < 2:
            raise ValueError("Nom kamida 2 ta belgidan iborat bo'lsin.")
        if not text:
            raise ValueError("Bo'sh bo'lmasin.")
        if len(text) > field.max_len:
            raise ValueError(f"Juda uzun ({len(text)}). Maksimum {field.max_len} belgi.")
        return text
    if field.kind == "genres":
        parts: list[str] = []
        for p in text.replace(";", ",").split(","):
            p = p.strip()
            if p and p.casefold() not in {x.casefold() for x in parts}:
                parts.append(p)
        if not parts:
            raise ValueError("Kamida bitta janr yuboring.")
        if len(parts) > 8 or any(len(p) > 30 for p in parts):
            raise ValueError("Ko'pi bilan 8 ta janr, har biri 30 belgigacha.")
        return ", ".join(parts)
    if field.kind in ("int", "float"):
        try:
            num = float(text.replace(",", "."))
        except ValueError:
            raise ValueError("Raqam yuboring.") from None
        if not (field.lo <= num <= field.hi):
            raise ValueError(f"Qiymat {field.lo:g} dan {field.hi:g} gacha bo'lsin.")
        if field.kind == "int":
            if num != int(num):
                raise ValueError("Butun son yuboring.")
            return int(num)
        return round(num, 1)
    raise ValueError("Bu maydon uchun matn qabul qilinmaydi.")


# ------------------------------------------------------------------ yordamchilar
def card_markup(row: dict[str, Any], page: int, repo: Repo) -> InlineKeyboardMarkup:
    aid = -row["id"]
    return an_card(row, page, repo.catalog.is_featured("rec", aid), repo.catalog.is_featured("pop", aid))


async def send_card(bot, chat_id: int, anime: dict[str, Any], markup: InlineKeyboardMarkup,
                    delete: Message | None = None) -> None:
    if delete is not None:
        try:
            await delete.delete()
        except TelegramBadRequest:
            pass
    caption = build_caption(anime)
    if image := get_image(anime):
        try:
            await bot.send_photo(chat_id, image, caption=caption, reply_markup=markup)
            return
        except TelegramBadRequest as exc:
            logger.warning("Admin kartochkasi rasmi yuborilmadi: %s", exc)
    await bot.send_message(chat_id, caption, reply_markup=markup)


async def render_card(event: Message | CallbackQuery, anime_id: int, page: int, repo: Repo) -> None:
    row = repo.catalog.get(anime_id)
    msg = event.message if isinstance(event, CallbackQuery) else event
    if not row:
        await show(event, "😕 Anime topilmadi (o'chirilgan bo'lishi mumkin).",
                   kb(back_row("◀️ Ro'yxat", "an", "list", page=1)))
        return
    await send_card(msg.bot, msg.chat.id, custom_to_jikan(row), card_markup(row, page, repo),
                    delete=msg if isinstance(event, CallbackQuery) else None)


def prompt_text(data: dict[str, Any], field: Field, repo: Repo) -> str:
    if data["mode"] == "add":
        head = f"➕ <b>Yangi anime</b> · {data['step'] + 1}/{len(FIELDS)}\n<b>{field.title}</b>\n\n"
        tail = ""
    else:
        head = f"✏️ <b>Tahrirlash</b> · {field.title}\n\n"
        row = repo.catalog.get(data["edit_id"]) or {}
        cur = row.get(field.key)
        tail = f"\n\n<i>Hozirgi qiymat:</i> {esc(str(cur)) if cur not in (None, '') else '—'}" \
            if field.kind != "photo" else ""
    return head + field.prompt + tail + "\n\n<i>Bekor qilish: /cancel</i>"


def prompt_markup(data: dict[str, Any], field: Field) -> InlineKeyboardMarkup:
    optional = not field.required
    clear = "🗑 Qiymatni tozalash" if data["mode"] == "edit" else None
    return form_kb(field.choices, optional, clear)


def current_field(data: dict[str, Any]) -> Field:
    return FIELDS[data["step"]] if data["mode"] == "add" else BY_KEY[data["edit_field"]]


async def ask(event: Message | CallbackQuery, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    field = current_field(data)
    await show(event, prompt_text(data, field, repo), prompt_markup(data, field))


async def finish_value(event: Message | CallbackQuery, state: FSMContext, repo: Repo,
                       admin: AdminInfo, value: Any) -> None:
    """Maydon qiymati qabul qilindi: qo'shishda keyingi qadam, tahrirda saqlash."""
    data = await state.get_data()
    field = current_field(data)
    msg = event.message if isinstance(event, CallbackQuery) else event
    if data["mode"] == "edit":
        aid = data["edit_id"]
        await repo.catalog.update(aid, field.key, value)
        await log_action(repo, admin, "anime_edit", f"#{aid}: {field.title}")
        await state.clear()
        await render_card(event, aid, data.get("page", 1), repo)
        return
    values = dict(data["values"])
    values[field.key] = value
    step = data["step"] + 1
    await state.update_data(values=values, step=step)
    if step < len(FIELDS):
        await ask(event, state, repo)
        return
    # barcha maydonlar to'ldirildi — ko'rib chiqish
    await send_card(msg.bot, msg.chat.id, custom_to_jikan({**values, "id": 0}), form_confirm(),
                    delete=msg if isinstance(event, CallbackQuery) else None)


async def stale(cb: CallbackQuery) -> None:
    await cb.answer("Sessiya tugagan. Qaytadan boshlang.", show_alert=True)


# ------------------------------------------------------------------ menyu va ro'yxat
@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "menu")))
async def an_home(cb: CallbackQuery, repo: Repo, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    c = repo.catalog
    await show(cb, "🎬 <b>Anime boshqaruvi</b>\n\nBu yerda qo'shilgan animelar botdagi qidiruvda "
                   "MyAnimeList natijalari bilan birga chiqadi.",
               an_menu(c.count(), len(c.featured("rec")), len(c.featured("pop"))))


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "list")))
async def an_list_page(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    pages = pages_for(repo.catalog.count())
    page = clamp_page(callback_data.page, pages)
    rows = repo.catalog.list_page(PER_PAGE, (page - 1) * PER_PAGE)
    text = f"📚 <b>Qo'shilgan animelar</b> — {repo.catalog.count()} ta"
    if not rows:
        text += "\n\n😕 Hozircha bo'sh. «➕ Qo'shish» tugmasini bosing."
    await show(cb, text, an_list(rows, page, pages))


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "view")))
async def an_view(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await render_card(cb, callback_data.id, callback_data.page, repo)


# ------------------------------------------------------------------ qo'shish
@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "add")))
async def add_start(cb: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(AnimeFormSG.input)
    await state.update_data(mode="add", step=0, values={})
    await ask(cb, state, repo)


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "edit")))
async def edit_start(cb: CallbackQuery, callback_data: AdmCB, state: FSMContext, repo: Repo) -> None:
    if callback_data.arg not in BY_KEY or not repo.catalog.get(callback_data.id):
        await cb.answer("Anime topilmadi", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(AnimeFormSG.input)
    await state.update_data(mode="edit", edit_id=callback_data.id, edit_field=callback_data.arg,
                            page=callback_data.page or 1)
    await ask(cb, state, repo)


@router.message(AnimeFormSG.input, F.photo)
async def got_photo(message: Message, state: FSMContext, repo: Repo, admin: AdminInfo) -> None:
    data = await state.get_data()
    if not data.get("mode"):
        await message.answer("Sessiya tugagan. /admin")
        return
    if current_field(data).kind != "photo":
        await message.answer("✏️ Hozir rasm emas, matn kutilmoqda.")
        return
    await finish_value(message, state, repo, admin, message.photo[-1].file_id)


@router.message(AnimeFormSG.input, F.text, ~F.text.startswith("/"))
async def got_text(message: Message, state: FSMContext, repo: Repo, admin: AdminInfo) -> None:
    data = await state.get_data()
    if not data.get("mode"):
        await message.answer("Sessiya tugagan. /admin")
        return
    field = current_field(data)
    if field.kind in ("choice", "photo"):
        hint = "Pastdagi tugmalardan birini tanlang." if field.kind == "choice" else "Rasm yuboring."
        await message.answer(f"⚠️ {hint}")
        return
    try:
        value = parse_value(field, message.text)
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}\nQayta yuboring.")
        return
    await finish_value(message, state, repo, admin, value)


@router.message(AnimeFormSG.input)
async def got_other(message: Message) -> None:
    await message.answer("⚠️ Bu turdagi xabar qabul qilinmaydi. Ko'rsatmaga qarang yoki /cancel.")


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "ch")))
async def pick_choice(cb: CallbackQuery, callback_data: AdmCB, state: FSMContext, repo: Repo,
                      admin: AdminInfo) -> None:
    data = await state.get_data()
    if not data.get("mode"):
        await stale(cb)
        return
    field = current_field(data)
    if field.kind != "choice" or callback_data.arg not in {v for v, _ in field.choices}:
        await cb.answer("Noto'g'ri tanlov", show_alert=True)
        return
    await cb.answer()
    await finish_value(cb, state, repo, admin, callback_data.arg)


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "skip")))
async def skip_field(cb: CallbackQuery, state: FSMContext, repo: Repo, admin: AdminInfo) -> None:
    data = await state.get_data()
    if not data.get("mode"):
        await stale(cb)
        return
    if current_field(data).required:
        await cb.answer("Bu maydon majburiy", show_alert=True)
        return
    await cb.answer()
    await finish_value(cb, state, repo, admin, None)


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "cancel")))
async def cancel_form(cb: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    await state.clear()
    await cb.answer("Bekor qilindi")
    if data.get("mode") == "edit":
        await render_card(cb, data["edit_id"], data.get("page", 1), repo)
    else:
        c = repo.catalog
        msg = cb.message
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
        await msg.bot.send_message(
            msg.chat.id, "🎬 <b>Anime boshqaruvi</b>",
            reply_markup=an_menu(c.count(), len(c.featured("rec")), len(c.featured("pop"))))


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "save")))
async def save(cb: CallbackQuery, state: FSMContext, repo: Repo, admin: AdminInfo) -> None:
    data = await state.get_data()
    if data.get("mode") != "add" or data.get("step") != len(FIELDS) or not data["values"].get("title"):
        await stale(cb)
        return
    new_id = await repo.catalog.add(data["values"], admin.user_id)
    await state.clear()
    await log_action(repo, admin, "anime_add", f"#{new_id}: {data['values']['title']}")
    await cb.answer("✅ Saqlandi")
    await render_card(cb, new_id, 1, repo)


# ------------------------------------------------------------------ o'chirish
@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "del")))
async def delete_ask(cb: CallbackQuery, callback_data: AdmCB, repo: Repo) -> None:
    row = repo.catalog.get(callback_data.id)
    if not row:
        await cb.answer("Anime topilmadi", show_alert=True)
        return
    await cb.answer()
    await show(cb, f"🗑 <b>O'chirishni tasdiqlang</b>\n\n🎬 <b>{esc(row['title'])}</b> (#{row['id']})\n\n"
                   "Anime katalogdan, tavsiya/mashhur ro'yxatlaridan va foydalanuvchilar sevimlilaridan "
                   "olib tashlanadi. Bu amalni qaytarib bo'lmaydi.",
               confirm_kb("an", "del_yes", "view", id=row["id"], yes_text="🗑 Ha, o'chirish"))


@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "del_yes")))
async def delete_do(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, storage: BaseStorage,
                    admin: AdminInfo) -> None:
    row = repo.catalog.get(callback_data.id)
    if not row or not await repo.catalog.delete(row["id"]):
        await cb.answer("Anime topilmadi", show_alert=True)
        return
    await storage.purge(-row["id"])
    await log_action(repo, admin, "anime_delete", f"#{row['id']}: {row['title']}")
    await cb.answer("🗑 O'chirildi")
    pages = pages_for(repo.catalog.count())
    await show(cb, f"🗑 <b>{esc(row['title'])}</b> o'chirildi.",
               an_list(repo.catalog.list_page(PER_PAGE, 0), 1, pages))


# ------------------------------------------------------------------ tavsiya / mashhur belgisi
@router.callback_query(AdmCB.filter((F.sec == "an") & (F.act == "feat")))
async def toggle_feature(cb: CallbackQuery, callback_data: AdmCB, repo: Repo, admin: AdminInfo) -> None:
    row = repo.catalog.get(callback_data.id)
    kind = callback_data.arg
    if not row or kind not in ("rec", "pop"):
        await cb.answer("Anime topilmadi", show_alert=True)
        return
    aid = -row["id"]
    name = "Tavsiya" if kind == "rec" else "Mashhur"
    if repo.catalog.is_featured(kind, aid):
        await repo.catalog.feature_remove(kind, aid)
        await log_action(repo, admin, "feature_remove", f"{name}: {row['title']}")
        await cb.answer(f"➖ {name} ro'yxatidan olindi")
    else:
        await repo.catalog.feature_add(kind, aid, row["title"], row.get("score"), admin.user_id)
        await log_action(repo, admin, "feature_add", f"{name}: {row['title']}")
        await cb.answer(f"✅ {name} ro'yxatiga qo'shildi")
    try:
        await cb.message.edit_reply_markup(reply_markup=card_markup(row, callback_data.page, repo))
    except TelegramBadRequest:
        pass

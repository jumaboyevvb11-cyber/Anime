"""📣 Xabar yuborish: matn / rasm, e'lon tugmasi, jarayon statistikasi."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import (back_row, bc_button_choice, bc_confirm, bc_history, bc_menu,
                                 bc_progress, cancel_kb, kb)
from bot.services.access import AdminInfo
from bot.services.broadcaster import Broadcaster, Job
from bot.services.repo import Repo
from bot.states import BroadcastSG
from bot.utils import timefmt
from bot.utils.text import esc

from .common import guard_router, log_action, show

router = Router(name="admin_broadcast")
guard_router(router, "broadcast")
logger = logging.getLogger(__name__)

STATUS_UZ = {"running": "⏳ Davom etmoqda", "done": "✅ Tugadi", "cancelled": "⏹ To'xtatildi",
             "error": "❌ Xato bilan tugadi", "interrupted": "⚠️ Bot qayta ishga tushgani sabab uzildi"}
KIND_UZ = {"text": "📝 Matn", "photo": "🖼 Rasm + matn"}


def progress_text(job: Job, final: bool) -> str:
    pct = int(100 * job.processed / job.total) if job.total else 100
    filled = pct // 10
    head = f"📡 <b>Xabar yuborish #{job.id}</b> — {STATUS_UZ.get(job.status, job.status)}"
    lines = [
        head, "",
        f"<code>{'█' * filled}{'░' * (10 - filled)}</code> <b>{pct}%</b>",
        f"👥 Jami qabul qiluvchi: <b>{job.total}</b>",
        f"✅ Yuborildi: <b>{job.sent}</b>",
        f"🚫 Botni bloklagan: <b>{job.blocked}</b>",
        f"⚠️ Xatolik (yuborilmadi): <b>{job.failed}</b>",
        f"⏱ Vaqt: <b>{timefmt.fmt_duration(job.elapsed)}</b>",
    ]
    if final and job.reasons:
        lines += ["", "<b>Yuborilmaganlar sababi:</b>"]
        lines += [f"• {esc(r)}: {n}" for r, n in job.reasons.most_common()]
    return "\n".join(lines)


def record_text(r: dict) -> str:
    return (
        f"📡 <b>Xabar yuborish #{r['id']}</b> — {STATUS_UZ.get(r['status'], r['status'])}\n\n"
        f"Turi: {KIND_UZ.get(r['kind'], r['kind'])}\n"
        f"Matn: <i>{esc(r['preview']) or '—'}</i>\n\n"
        f"👥 Jami: <b>{r['total']}</b>\n"
        f"✅ Yuborildi: <b>{r['sent']}</b>\n"
        f"🚫 Botni bloklagan: <b>{r['blocked']}</b>\n"
        f"⚠️ Xatolik: <b>{r['failed']}</b>\n"
        f"🕒 Boshlandi: {timefmt.fmt_dt(r['started_at'])}\n"
        f"🏁 Tugadi: {timefmt.fmt_dt(r['finished_at'])}"
    )


def valid_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.netloc) and " " not in url and len(url) <= 500


def parse_button(text: str) -> tuple[str, str] | None:
    if "|" not in text:
        return None
    label, url = (x.strip() for x in text.split("|", 1))
    if not label or len(label) > 60 or not valid_url(url):
        return None
    return label, url


def build_markup(data: dict) -> InlineKeyboardMarkup | None:
    if data.get("btn_text") and data.get("btn_url"):
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=data["btn_text"], url=data["btn_url"])]])
    return None


# ------------------------------------------------------------------ menyu
@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "menu")))
async def bc_home(cb: CallbackQuery, repo: Repo, broadcaster: Broadcaster, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    count = len(await repo.users.broadcast_ids())
    text = (f"📣 <b>Xabar yuborish</b>\n\nQabul qiluvchilar: <b>{count}</b> ta faol foydalanuvchi.\n"
            "Matn, rasm (izoh bilan) yoki reklama/e'lon yuborishingiz mumkin.")
    if broadcaster.busy:
        text += "\n\n⏳ <b>Hozir yuborish jarayoni ketmoqda.</b>"
    await show(cb, text, bc_menu(broadcaster.busy))


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "new")))
async def bc_new(cb: CallbackQuery, broadcaster: Broadcaster, state: FSMContext) -> None:
    if broadcaster.busy:
        await cb.answer("Hozir boshqa yuborish ketmoqda. Tugashini kuting yoki to'xtating.", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(BroadcastSG.content)
    await show(cb, "✍️ <b>Yangi xabar</b>\n\nYuboriladigan <b>matn</b> yoki <b>rasm</b> (izoh bilan) ni shu yerga yuboring.\n"
                   "Formatlash (qalin, kursiv, havola) saqlanadi.\n\nBekor qilish: /cancel",
               cancel_kb("bc", "cancel"))


async def _got_content(message: Message, state: FSMContext, kind: str) -> None:
    preview = (message.text or message.caption or "")
    await state.update_data(from_chat_id=message.chat.id, message_id=message.message_id,
                            kind=kind, preview=preview[:100], btn_text=None, btn_url=None)
    await state.set_state(None)
    await message.answer("🔗 Xabar ostiga havola-tugma (masalan «Ko'rish») qo'shasizmi?",
                         reply_markup=bc_button_choice())


@router.message(BroadcastSG.content, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    await _got_content(message, state, "photo")


@router.message(BroadcastSG.content, F.text, ~F.text.startswith("/"))
async def got_text(message: Message, state: FSMContext) -> None:
    await _got_content(message, state, "text")


@router.message(BroadcastSG.content)
async def got_wrong(message: Message) -> None:
    await message.answer("⚠️ Faqat matn yoki rasm (izoh bilan) yuborish mumkin. Qayta yuboring yoki /cancel.")


# ------------------------------------------------------------------ tugma
@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "addbtn")))
async def add_button(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("message_id"):
        await cb.answer("Sessiya tugagan. Qaytadan boshlang.", show_alert=True)
        return
    await cb.answer()
    await state.set_state(BroadcastSG.button)
    await show(cb, "🔗 Tugmani shu formatda yuboring:\n\n<code>Tugma matni | https://havola.uz</code>",
               cancel_kb("bc", "cancel"))


@router.message(BroadcastSG.button, F.text, ~F.text.startswith("/"))
async def got_button(message: Message, state: FSMContext, repo: Repo) -> None:
    parsed = parse_button(message.text)
    if not parsed:
        await message.answer("⚠️ Format noto'g'ri. Misol: <code>Ko'rish | https://t.me/kanal</code>\n"
                             "(havola http:// yoki https:// bilan boshlansin)")
        return
    await state.update_data(btn_text=parsed[0], btn_url=parsed[1])
    await state.set_state(None)
    await send_preview(message, state, repo)


@router.message(BroadcastSG.button)
async def button_wrong(message: Message) -> None:
    await message.answer("✏️ Matn ko'rinishida yuboring: <code>Tugma | https://havola</code> (yoki /cancel)")


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "skipbtn")))
async def skip_button(cb: CallbackQuery, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    if not data.get("message_id"):
        await cb.answer("Sessiya tugagan. Qaytadan boshlang.", show_alert=True)
        return
    await cb.answer()
    await send_preview(cb.message, state, repo)


async def send_preview(message: Message, state: FSMContext, repo: Repo) -> None:
    data = await state.get_data()
    chat_id = message.chat.id
    try:
        await message.bot.copy_message(chat_id=chat_id, from_chat_id=data["from_chat_id"],
                                       message_id=data["message_id"], reply_markup=build_markup(data))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ko'rib chiqish yuborilmadi: %s", exc)
        await state.clear()
        await message.bot.send_message(chat_id, "⚠️ Xabarni ko'rsatib bo'lmadi (o'chirilgan bo'lishi mumkin). "
                                                "Qaytadan boshlang.", reply_markup=kb(back_row("◀️ Orqaga", "bc")))
        return
    count = len(await repo.users.broadcast_ids())
    await message.bot.send_message(
        chat_id, f"👆 <b>Xabar shunday ko'rinadi.</b>\n\n👥 Qabul qiluvchilar: <b>{count}</b> ta\n\n"
                 "Hammaga yuborilsinmi?", reply_markup=bc_confirm())


# ------------------------------------------------------------------ yuborish
@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "go")))
async def go(cb: CallbackQuery, admin: AdminInfo, state: FSMContext, repo: Repo,
             broadcaster: Broadcaster) -> None:
    data = await state.get_data()
    if not data.get("message_id"):
        await cb.answer("Sessiya tugagan. Qaytadan boshlang.", show_alert=True)
        return
    if broadcaster.busy:
        await cb.answer("Hozir boshqa yuborish ketmoqda.", show_alert=True)
        return
    chat_id, msg_id = cb.message.chat.id, cb.message.message_id
    bot = cb.bot

    async def notify(job: Job, final: bool) -> None:
        await bot.edit_message_text(progress_text(job, final), chat_id=chat_id, message_id=msg_id,
                                    reply_markup=bc_progress(job.id, not final))
        if final:
            await log_action(repo, admin, "broadcast_end",
                             f"#{job.id}: {job.sent}/{job.total} yuborildi, {job.blocked} blok, {job.failed} xato "
                             f"({job.status})")
            await bot.send_message(chat_id, f"📬 Yuborish #{job.id} yakunlandi: ✅ {job.sent} · 🚫 {job.blocked} · "
                                            f"⚠️ {job.failed}")

    job = await broadcaster.start(admin.user_id, data["from_chat_id"], data["message_id"],
                                  build_markup(data), data["kind"], data.get("preview", ""), notify)
    if not job:
        await cb.answer("Hozir boshqa yuborish ketmoqda.", show_alert=True)
        return
    await state.clear()
    await cb.answer("🚀 Boshlandi")
    await log_action(repo, admin, "broadcast_start", f"#{job.id}: {job.total} ta qabul qiluvchi")
    await show(cb, progress_text(job, False), bc_progress(job.id, True))


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "stop")))
async def stop(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo,
               broadcaster: Broadcaster) -> None:
    if broadcaster.stop(callback_data.id):
        await log_action(repo, admin, "broadcast_stop", f"#{callback_data.id}")
        await cb.answer("⏹ To'xtatilmoqda...")
    else:
        await cb.answer("Bu yuborish allaqachon tugagan.", show_alert=True)


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "status")))
async def status(cb: CallbackQuery, broadcaster: Broadcaster) -> None:
    job = broadcaster.current
    if not job:
        await cb.answer("Faol jarayon yo'q.", show_alert=True)
        return
    await cb.answer()
    await show(cb, progress_text(job, job.status != "running"), bc_progress(job.id, job.status == "running"))


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "cancel")))
async def cancel(cb: CallbackQuery, state: FSMContext, repo: Repo, broadcaster: Broadcaster) -> None:
    await bc_home(cb, repo, broadcaster, state)


# ------------------------------------------------------------------ tarix
@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "hist")))
async def history(cb: CallbackQuery, repo: Repo) -> None:
    await cb.answer()
    rows = await repo.broadcasts.recent(10)
    text = "📜 <b>Yuborishlar tarixi</b>" + ("" if rows else "\n\nHozircha bo'sh.")
    await show(cb, text, bc_history(rows))


@router.callback_query(AdmCB.filter((F.sec == "bc") & (F.act == "view")))
async def view(cb: CallbackQuery, callback_data: AdmCB, repo: Repo) -> None:
    r = await repo.broadcasts.get(callback_data.id)
    if not r:
        await cb.answer("Topilmadi", show_alert=True)
        return
    await cb.answer()
    await show(cb, record_text(r), kb(back_row("◀️ Tarix", "bc", "hist")))

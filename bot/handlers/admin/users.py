"""👥 Foydalanuvchilarni boshqarish."""
from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import (UNKNOWN, back_row, cancel_kb, confirm_kb, kb, user_card,
                                 users_list, users_menu)
from bot.services.access import AccessService, AdminInfo
from bot.services.repo import Repo
from bot.services.storage import BaseStorage
from bot.states import UserSearchSG
from bot.utils import timefmt
from bot.utils.text import esc

from .common import PER_PAGE, clamp_page, guard_router, log_action, mention, notify_user, pages_for, show

router = Router(name="admin_users")
guard_router(router, "users")

FILTER_TITLES = {"all": "Barcha foydalanuvchilar", "new": "Bugun qo'shilganlar", "blk": "Bloklanganlar"}


def status_line(u: dict[str, Any], access: AccessService) -> str:
    if access.is_admin(u["user_id"]):
        return "🛡 Admin"
    if u["is_blocked"]:
        return f"🚫 Bloklangan ({timefmt.fmt_dt(u['blocked_at'])})"
    if u["bot_blocked"]:
        return "😴 Botni to'xtatgan"
    return "✅ Faol"


async def card_text(u: dict[str, Any], repo: Repo, storage: BaseStorage, access: AccessService) -> str:
    searches = await repo.searches.user_count(u["user_id"])
    favs = await storage.count(u["user_id"])
    return (
        "👤 <b>Foydalanuvchi</b>\n\n"
        f"{mention(u['name'], u['user_id'], u.get('username'))}\n"
        f"📅 Qo'shilgan: {timefmt.fmt_dt(u['joined_at'])}\n"
        f"🕒 Oxirgi faollik: {timefmt.fmt_dt(u['last_active'])} ({timefmt.ago(u['last_active'])})\n"
        f"🔍 Qidiruvlar: <b>{searches}</b>\n"
        f"⭐ Sevimlilar: <b>{favs}</b>\n"
        f"📌 Holat: {status_line(u, access)}"
    )


def cannot_manage(admin: AdminInfo, target_id: int, access: AccessService) -> str | None:
    if target_id == admin.user_id:
        return "O'zingizni bloklab bo'lmaydi."
    if access.is_admin(target_id):
        return "Adminlarni bloklab bo'lmaydi. Avval adminlikdan olib tashlang."
    return None


async def render_view(cb: Message | CallbackQuery, uid: int, page: int, flt: str, admin: AdminInfo,
                      repo: Repo, storage: BaseStorage, access: AccessService) -> None:
    u = await repo.users.get(uid)
    if not u:
        await show(cb, "😕 Foydalanuvchi topilmadi.", kb(back_row("◀️ Orqaga", "users")))
        return
    can = cannot_manage(admin, uid, access) is None
    await show(cb, await card_text(u, repo, storage, access), user_card(u, page, flt, can))


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "menu")))
async def users_home(cb: CallbackQuery, repo: Repo, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    total = await repo.users.total()
    blocked = await repo.users.blocked_count()
    await show(cb, f"👥 <b>Foydalanuvchilar</b>\n\nJami: <b>{total}</b> · Bloklangan: <b>{blocked}</b>",
               users_menu(blocked))


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "list")))
async def users_page(cb: CallbackQuery, callback_data: AdmCB, repo: Repo) -> None:
    await cb.answer()
    flt = callback_data.arg if callback_data.arg in FILTER_TITLES else "all"
    total = await repo.users.count(flt)
    pages = pages_for(total)
    page = clamp_page(callback_data.page, pages)
    rows = await repo.users.page(flt, PER_PAGE, (page - 1) * PER_PAGE)
    head = f"👥 <b>{FILTER_TITLES[flt]}</b> — {total} ta"
    if not rows:
        head += "\n\n😕 Hech narsa topilmadi."
    else:
        head += "\n🟢 faol · 😴 botni to'xtatgan · 🚫 bloklangan"
    await show(cb, head, users_list(rows, page, pages, flt))


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "view")))
async def user_view(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo,
                    storage: BaseStorage, access: AccessService) -> None:
    await cb.answer()
    await render_view(cb, callback_data.id, callback_data.page, callback_data.arg, admin,
                      repo, storage, access)


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "act")))
async def user_activity(cb: CallbackQuery, callback_data: AdmCB, repo: Repo) -> None:
    await cb.answer()
    u = await repo.users.get(callback_data.id)
    if not u:
        await show(cb, "😕 Foydalanuvchi topilmadi.", kb(back_row("◀️ Orqaga", "users")))
        return
    total = await repo.searches.user_count(u["user_id"])
    recent = await repo.searches.user_recent(u["user_id"], 15)
    lines = [f"📜 <b>Faollik</b> — {mention(u['name'], u['user_id'], u.get('username'))}", "",
             f"🕒 Oxirgi faollik: {timefmt.fmt_dt(u['last_active'])}",
             f"🔍 Jami qidiruvlar: <b>{total}</b>", "", "<b>Oxirgi qidiruvlar:</b>"]
    if recent:
        for r in recent:
            lines.append(f"<code>{timefmt.fmt_short(r['ts'])}</code> {esc(r['term'])} → {r['results']} ta natija")
    else:
        lines.append("Hozircha qidiruv yo'q.")
    markup = kb([
        _back("◀️ Foydalanuvchi", u["user_id"], callback_data.page, callback_data.arg),
    ])
    await show(cb, "\n".join(lines), markup)


def _back(text: str, uid: int, page: int, flt: str):
    from bot.keyboards_admin import b
    return b(text, "users", "view", id=uid, page=page, arg=flt)


# ------------------------------------------------------------------ bloklash / blokdan chiqarish
@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "block")))
async def block_ask(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo,
                    access: AccessService) -> None:
    u = await repo.users.get(callback_data.id)
    if not u:
        await cb.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    if (why := cannot_manage(admin, u["user_id"], access)):
        await cb.answer(why, show_alert=True)
        return
    await cb.answer()
    await show(cb, f"🚫 <b>Bloklashni tasdiqlang</b>\n\n{mention(u['name'], u['user_id'], u.get('username'))}\n\n"
                   "Bloklangan foydalanuvchi botdan foydalana olmaydi va e'lonlarni olmaydi.",
               confirm_kb("users", "block_yes", "view", id=u["user_id"], arg=callback_data.arg,
                          no_arg=callback_data.arg, page=callback_data.page, yes_text="🚫 Ha, bloklash"))


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "block_yes")))
async def block_do(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo,
                   storage: BaseStorage, access: AccessService) -> None:
    uid = callback_data.id
    if (why := cannot_manage(admin, uid, access)):  # amal oldidan qayta tekshiruv
        await cb.answer(why, show_alert=True)
        return
    if not await repo.users.set_blocked(uid, True, admin.user_id):
        await cb.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    await log_action(repo, admin, "user_block", f"ID {uid}")
    await cb.answer("🚫 Bloklandi")
    await render_view(cb, uid, callback_data.page, callback_data.arg, admin, repo, storage, access)


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "unblock")))
async def unblock_ask(cb: CallbackQuery, callback_data: AdmCB, repo: Repo) -> None:
    u = await repo.users.get(callback_data.id)
    if not u:
        await cb.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    await cb.answer()
    await show(cb, f"✅ <b>Blokdan chiqarishni tasdiqlang</b>\n\n{mention(u['name'], u['user_id'], u.get('username'))}",
               confirm_kb("users", "unblock_yes", "view", id=u["user_id"], arg=callback_data.arg,
                          no_arg=callback_data.arg, page=callback_data.page, yes_text="✅ Ha, chiqarish"))


@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "unblock_yes")))
async def unblock_do(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo,
                     storage: BaseStorage, access: AccessService) -> None:
    uid = callback_data.id
    if not await repo.users.set_blocked(uid, False, admin.user_id):
        await cb.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    await log_action(repo, admin, "user_unblock", f"ID {uid}")
    await notify_user(cb.bot, uid, "✅ Siz botdan foydalanish uchun blokdan chiqarildingiz.")
    await cb.answer("✅ Blokdan chiqarildi")
    await render_view(cb, uid, callback_data.page, callback_data.arg, admin, repo, storage, access)


# ------------------------------------------------------------------ qidirish
@router.callback_query(AdmCB.filter((F.sec == "users") & (F.act == "search")))
async def search_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(UserSearchSG.waiting)
    await show(cb, "🔎 <b>Foydalanuvchini qidirish</b>\n\nTelegram ID yoki @username yuboring.\n"
                   "Bekor qilish: /cancel", cancel_kb("users", "menu"))


@router.message(UserSearchSG.waiting, F.text, ~F.text.startswith("/"))
async def search_do(message: Message, admin: AdminInfo, repo: Repo, storage: BaseStorage,
                    access: AccessService, state: FSMContext) -> None:
    u = await repo.users.find(message.text)
    if not u:
        await message.answer("😕 Topilmadi. Foydalanuvchi botdan kamida bir marta foydalangan bo'lishi kerak.\n"
                             "Boshqa ID yoki @username yuboring yoki /cancel.",
                             reply_markup=cancel_kb("users", "menu"))
        return
    await state.clear()
    await render_view(message, u["user_id"], 0, "all", admin, repo, storage, access)


@router.message(UserSearchSG.waiting)
async def search_wrong_input(message: Message) -> None:
    await message.answer("✏️ Iltimos, matn ko'rinishida ID yoki @username yuboring (yoki /cancel).")

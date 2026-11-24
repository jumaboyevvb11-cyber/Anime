"""Admin panelning bosh menyusi, /admin, /cancel va yopish."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards import main_menu
from bot.keyboards_admin import BTN_ADMIN, main_menu as admin_menu
from bot.services.access import AccessService, AdminInfo
from bot.services.repo import Repo
from bot.services.stats import StatsService
from bot.utils.text import esc

from .common import IsAdmin, guard_router, show

router = Router(name="admin_panel")
guard_router(router, None)


async def menu_text(admin: AdminInfo, stats: StatsService) -> str:
    role = "👑 Super Admin" if admin.is_super else "🛡 Admin"
    lines = [f"🛠 <b>Admin panel</b>", f"{role}: <b>{esc(admin.name or '—')}</b>", ""]
    if admin.can("stats"):
        o = await stats.overview()
        lines += [
            f"👥 Foydalanuvchilar: <b>{o['total']}</b> (bugun +{o['new_today']})",
            f"🟢 Faol (24 soat): <b>{o['active_24h']}</b>",
            f"🔍 Bugungi qidiruvlar: <b>{o['searches_today']}</b>",
            "",
        ]
    lines.append("Bo'limni tanlang 👇")
    return "\n".join(lines)


async def open_panel(event: Message | CallbackQuery, admin: AdminInfo, stats: StatsService,
                     state: FSMContext) -> None:
    await state.clear()
    await show(event, await menu_text(admin, stats), admin_menu(admin))


@router.message(Command("admin"))
@router.message(F.text == BTN_ADMIN)
async def cmd_admin(message: Message, admin: AdminInfo, stats: StatsService,
                    state: FSMContext) -> None:
    await open_panel(message, admin, stats, state)


@router.message(Command("cancel"), IsAdmin())
async def cmd_cancel(message: Message, admin: AdminInfo, stats: StatsService,
                     state: FSMContext) -> None:
    had = await state.get_state()
    await state.clear()
    await message.answer("❌ Bekor qilindi." if had else "ℹ️ Bekor qilinadigan amal yo'q.",
                         reply_markup=main_menu(is_admin=True))
    await message.answer(await menu_text(admin, stats), reply_markup=admin_menu(admin))


@router.callback_query(AdmCB.filter((F.sec == "home") & (F.act == "menu")))
async def cb_home(cb: CallbackQuery, admin: AdminInfo, stats: StatsService,
                  state: FSMContext) -> None:
    await cb.answer()
    await open_panel(cb, admin, stats, state)


@router.callback_query(AdmCB.filter((F.sec == "home") & (F.act == "close")))
async def cb_close(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer("Yopildi")
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:  # noqa: BLE001
        pass

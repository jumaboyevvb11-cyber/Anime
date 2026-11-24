"""📜 Admin harakatlari tarixi."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import log_page
from bot.services.access import AdminInfo
from bot.services.repo import Repo
from bot.utils import timefmt
from bot.utils.text import esc

from .common import ACTION_LABELS, clamp_page, guard_router, pages_for, show

router = Router(name="admin_logs")
guard_router(router, "admins")

LOG_PER_PAGE = 8


@router.callback_query(AdmCB.filter((F.sec == "log") & (F.act == "list")))
async def logs_list(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, repo: Repo) -> None:
    await cb.answer()
    arg = "me" if callback_data.arg == "me" else "all"
    only = admin.user_id if arg == "me" else None
    total = await repo.logs.count(only)
    pages = pages_for(total, LOG_PER_PAGE)
    page = clamp_page(callback_data.page, pages)
    rows = await repo.logs.page(LOG_PER_PAGE, (page - 1) * LOG_PER_PAGE, only)
    lines = [f"📜 <b>Admin harakatlari tarixi</b> — {total} ta", ""]
    if not rows:
        lines.append("Hozircha yozuv yo'q.")
    for r in rows:
        label = ACTION_LABELS.get(r["action"], r["action"])
        detail = f"\n    <i>{esc(r['details'])}</i>" if r["details"] else ""
        lines.append(f"<code>{timefmt.fmt_short(r['ts'])}</code> <b>{esc(r['admin_name'] or str(r['admin_id']))}</b>\n"
                     f"  {label}{detail}")
    await show(cb, "\n".join(lines), log_page(page, pages, arg))

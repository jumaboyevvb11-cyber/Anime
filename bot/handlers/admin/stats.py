"""📊 Statistika bo'limi (har bir sahifa alohida)."""
from __future__ import annotations

import time

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import stats_menu, stats_page
from bot.services.stats import StatsService
from bot.utils import timefmt
from bot.utils.text import esc

from .common import guard_router, show

router = Router(name="admin_stats")
guard_router(router, "stats")

PERIOD_NAMES = {"d": "bugun", "w": "oxirgi 7 kun", "m": "oxirgi 30 kun"}


def bar(value: int, maximum: int, width: int = 10) -> str:
    if maximum <= 0:
        return "░" * width
    filled = round(width * value / maximum)
    return "█" * filled + "░" * (width - filled)


def fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", " ")


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "menu")))
async def stats_home(cb: CallbackQuery) -> None:
    await cb.answer()
    await show(cb, "📊 <b>Statistika</b>\n\nQaysi sahifani ko'rmoqchisiz?", stats_menu())


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "ov")))
async def stats_overview(cb: CallbackQuery, stats: StatsService) -> None:
    await cb.answer("Yangilandi")
    o = await stats.overview()
    text = (
        "📈 <b>Umumiy statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{fmt_num(o['total'])}</b>\n"
        f"🆕 Bugun yangi: <b>{o['new_today']}</b>  ·  7 kunda: <b>{o['new_week']}</b>\n\n"
        "🟢 <b>Faol foydalanuvchilar</b>\n"
        f"  • 24 soat: <b>{o['active_24h']}</b>\n"
        f"  • 7 kun: <b>{o['active_7d']}</b>\n"
        f"  • 30 kun: <b>{o['active_30d']}</b>\n\n"
        f"🔍 Jami qidiruvlar: <b>{fmt_num(o['searches_total'])}</b>\n"
        f"  • Bugun: <b>{o['searches_today']}</b>  ·  7 kunda: <b>{o['searches_week']}</b>\n\n"
        f"🚫 Bloklangan: <b>{o['blocked']}</b>  ·  😴 Botni to'xtatgan: <b>{o['bot_blocked']}</b>\n\n"
        f"🕒 <i>{timefmt.fmt_dt(timefmt.now())}</i>"
    )
    await show(cb, text, stats_page("ov"))


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "us")))
async def stats_users(cb: CallbackQuery, stats: StatsService) -> None:
    await cb.answer("Yangilandi")
    d = await stats.users_page()
    o = d["overview"]
    peak = max([max(u, s) for _, u, s in d["days"]] + [1])
    lines = ["👥 <b>Foydalanuvchilar statistikasi</b>", "", "📅 <b>Oxirgi 7 kun</b> (yangi · qidiruv)"]
    for day, new, searches in d["days"]:
        lines.append(f"<code>{day}</code> {bar(new, peak, 8)} <b>{new}</b> · {searches}")
    lines += [
        "",
        f"👥 Jami: <b>{fmt_num(o['total'])}</b>",
        f"🟢 Faol 24 soat / 7 kun / 30 kun: <b>{o['active_24h']}</b> / <b>{o['active_7d']}</b> / <b>{o['active_30d']}</b>",
        f"🚫 Bloklangan: <b>{o['blocked']}</b>",
        f"😴 Botni to'xtatgan: <b>{o['bot_blocked']}</b>",
    ]
    await show(cb, "\n".join(lines), stats_page("us"))


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "se")))
async def stats_searches(cb: CallbackQuery, callback_data: AdmCB, stats: StatsService) -> None:
    await cb.answer("Yangilandi")
    period = callback_data.arg if callback_data.arg in PERIOD_NAMES else "d"
    d = await stats.searches_page(period)
    lines = [
        f"🔍 <b>Qidiruvlar</b> — {PERIOD_NAMES[period]}", "",
        f"🔎 Qidiruvlar soni: <b>{fmt_num(d['count'])}</b>",
        f"👤 Qidirgan foydalanuvchilar: <b>{d['unique']}</b>",
        f"📚 Jami (butun davr): <b>{fmt_num(d['total'])}</b>", "",
        "🏆 <b>Eng ko'p qidirilganlar</b>",
    ]
    if d["terms"]:
        top = d["terms"][0]["c"]
        for n, t in enumerate(d["terms"], start=1):
            lines.append(f"{n}. {esc(t['term'])} — <b>{t['c']}</b> {bar(t['c'], top, 6)}")
    else:
        lines.append("Hozircha ma'lumot yo'q.")
    await show(cb, "\n".join(lines), stats_page("se", period))


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "an")))
async def stats_animes(cb: CallbackQuery, stats: StatsService) -> None:
    await cb.answer("Yangilandi")
    rows = await stats.animes_page()
    lines = ["🔥 <b>Eng ko'p ko'rilgan animelar</b>", ""]
    if rows:
        top = rows[0]["views"]
        for n, r in enumerate(rows, start=1):
            lines.append(f"{n}. {esc(r['title'])} — <b>{r['views']}</b> {bar(r['views'], top, 6)}")
    else:
        lines.append("Hozircha ma'lumot yo'q.")
    await show(cb, "\n".join(lines), stats_page("an"))


@router.callback_query(AdmCB.filter((F.sec == "stats") & (F.act == "bot")))
async def stats_bot(cb: CallbackQuery, stats: StatsService, started_at: float) -> None:
    await cb.answer("Yangilandi")
    d = await stats.bot_page(started_at)
    o = d["overview"]
    text = (
        "🤖 <b>Botning umumiy holati</b>\n\n"
        f"⏱ Ishlash vaqti: <b>{timefmt.fmt_duration(d['uptime'])}</b>\n"
        f"🗄 Baza: <b>{esc(d['db'])}</b>\n"
        f"🐍 Python <b>{d['python']}</b> · aiogram <b>{d['aiogram']}</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{fmt_num(o['total'])}</b>\n"
        f"🔍 Qidiruvlar: <b>{fmt_num(o['searches_total'])}</b>\n"
        f"⭐ Sevimlilar (jami): <b>{fmt_num(d['favorites'])}</b>\n"
        f"🎬 Qo'shilgan animelar: <b>{d['custom_anime']}</b>\n"
        f"📌 Tavsiya: <b>{d['rec']}</b> · Mashhur: <b>{d['pop']}</b>\n"
        f"🛡 Adminlar: <b>{d['admins']}</b>\n"
        f"📣 Yuborilgan e'lonlar: <b>{d['broadcasts']}</b>\n"
        f"💾 API kesh: <b>{d['cache']}</b> yozuv"
    )
    await show(cb, text, stats_page("bot"))

"""Admin panel klaviaturalari (inline)."""
from __future__ import annotations

from typing import Any, Iterable

from aiogram.types import InlineKeyboardButton as Btn, InlineKeyboardMarkup

from bot.callbacks_admin import AdmCB
from bot.services.access import PERMS, AdminInfo
from bot.utils.text import button_label

from bot.keyboards import BTN_ADMIN  # noqa: F401  (bitta manba)
UNKNOWN = "Noma'lum"


def b(text: str, sec: str, act: str = "menu", id: int = 0, page: int = 0, arg: str = "") -> Btn:
    return Btn(text=text, callback_data=AdmCB(sec=sec, act=act, id=id, page=page, arg=arg).pack())


def kb(*rows: Iterable[Btn]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[list(r) for r in rows if r])


def home_btn() -> Btn:
    return b("🏠 Admin panel", "home")


def back_row(text: str, sec: str, act: str = "menu", **kw: Any) -> list[Btn]:
    return [b(text, sec, act, **kw), home_btn()]


def cancel_kb(sec: str, act: str = "cancel") -> InlineKeyboardMarkup:
    return kb([b("❌ Bekor qilish", sec, act)])


def confirm_kb(sec: str, yes_act: str, no_act: str, id: int = 0, no_id: int | None = None,
               arg: str = "", yes_text: str = "✅ Ha, tasdiqlayman", no_arg: str = "",
               page: int = 0) -> InlineKeyboardMarkup:
    return kb([
        b(yes_text, sec, yes_act, id=id, arg=arg, page=page),
        b("❌ Yo'q, bekor qilish", sec, no_act, id=id if no_id is None else no_id, arg=no_arg, page=page),
    ])


def pager(sec: str, act: str, page: int, pages: int, arg: str = "") -> list[Btn]:
    row: list[Btn] = []
    if page > 1:
        row.append(b("◀️", sec, act, page=page - 1, arg=arg))
    row.append(Btn(text=f"📄 {page}/{pages}", callback_data="noop"))
    if page < pages:
        row.append(b("▶️", sec, act, page=page + 1, arg=arg))
    return row


# ------------------------------------------------------------------ bosh menyu
def main_menu(admin: AdminInfo) -> InlineKeyboardMarkup:
    cells = [
        ("stats", b("📊 Statistika", "stats")),
        ("users", b("👥 Foydalanuvchilar", "users")),
        ("broadcast", b("📣 Xabar yuborish", "bc")),
        ("anime", b("🎬 Anime boshqaruvi", "an")),
        ("admins", b("⚙️ Adminlar", "adm")),
        ("admins", b("📜 Harakatlar tarixi", "log", "list", page=1, arg="all")),
    ]
    btns = [c for perm, c in cells if admin.can(perm)]
    rows = [btns[i:i + 2] for i in range(0, len(btns), 2)]
    rows.append([b("❌ Yopish", "home", "close")])
    return kb(*rows)


# ------------------------------------------------------------------ statistika
def stats_menu() -> InlineKeyboardMarkup:
    return kb(
        [b("📈 Umumiy", "stats", "ov"), b("👥 Foydalanuvchilar", "stats", "us")],
        [b("🔍 Qidiruvlar", "stats", "se", arg="d"), b("🔥 Top animelar", "stats", "an")],
        [b("🤖 Bot holati", "stats", "bot")],
        [home_btn()],
    )


def stats_page(act: str, arg: str = "") -> InlineKeyboardMarkup:
    rows = []
    if act == "se":
        names = {"d": "Bugun", "w": "7 kun", "m": "30 kun"}
        rows.append([b(("• " if arg == k else "") + v, "stats", "se", arg=k) for k, v in names.items()])
    rows.append([b("🔄 Yangilash", "stats", act, arg=arg)])
    rows.append(back_row("◀️ Statistika", "stats"))
    return kb(*rows)


# ------------------------------------------------------------------ foydalanuvchilar
def users_menu(blocked: int) -> InlineKeyboardMarkup:
    return kb(
        [b("📋 Barcha foydalanuvchilar", "users", "list", page=1, arg="all")],
        [b("🆕 Bugun qo'shilganlar", "users", "list", page=1, arg="new")],
        [b(f"🚫 Bloklanganlar ({blocked})", "users", "list", page=1, arg="blk")],
        [b("🔎 ID / @username bo'yicha qidirish", "users", "search")],
        [home_btn()],
    )


def user_label(u: dict[str, Any]) -> str:
    mark = "🚫" if u["is_blocked"] else ("😴" if u["bot_blocked"] else "🟢")
    uname = f" @{u['username']}" if u.get("username") else ""
    label = f"{mark} {u['name'] or UNKNOWN}{uname} · {u['user_id']}"
    return label if len(label) <= 60 else label[:57] + "…"


def users_list(rows: list[dict[str, Any]], page: int, pages: int, flt: str) -> InlineKeyboardMarkup:
    out = [[b(user_label(u), "users", "view", id=u["user_id"], page=page, arg=flt)] for u in rows]
    if pages > 1:
        out.append(pager("users", "list", page, pages, flt))
    out.append(back_row("◀️ Orqaga", "users"))
    return kb(*out)


def user_card(u: dict[str, Any], page: int, flt: str, can_manage: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_manage:
        if u["is_blocked"]:
            rows.append([b("✅ Blokdan chiqarish", "users", "unblock", id=u["user_id"], page=page, arg=flt)])
        else:
            rows.append([b("🚫 Bloklash", "users", "block", id=u["user_id"], page=page, arg=flt)])
    rows.append([b("📜 Faollik", "users", "act", id=u["user_id"], page=page, arg=flt)])
    rows.append([b("◀️ Ro'yxat", "users", "list", page=max(page, 1), arg=flt or "all"), home_btn()])
    return kb(*rows)


# ------------------------------------------------------------------ xabar yuborish
def bc_menu(running: bool) -> InlineKeyboardMarkup:
    rows = [[b("✍️ Yangi xabar", "bc", "new")]]
    if running:
        rows.append([b("📡 Joriy jarayon", "bc", "status")])
    rows += [[b("📜 Yuborishlar tarixi", "bc", "hist")], [home_btn()]]
    return kb(*rows)


def bc_button_choice() -> InlineKeyboardMarkup:
    return kb(
        [b("🔗 Tugma qo'shish", "bc", "addbtn")],
        [b("⏭ Tugmasiz davom etish", "bc", "skipbtn")],
        [b("❌ Bekor qilish", "bc", "cancel")],
    )


def bc_confirm() -> InlineKeyboardMarkup:
    return kb(
        [b("✅ Hammaga yuborish", "bc", "go")],
        [b("❌ Bekor qilish", "bc", "cancel")],
    )


def bc_progress(job_id: int, running: bool) -> InlineKeyboardMarkup:
    if running:
        return kb([b("⏹ To'xtatish", "bc", "stop", id=job_id)])
    return kb([b("📜 Tarix", "bc", "hist"), home_btn()])


def bc_history(rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    from bot.utils import timefmt
    out = [[b(f"#{r['id']} · {timefmt.fmt_short(r['started_at'])} · {r['sent']}/{r['total']}",
              "bc", "view", id=r["id"])] for r in rows]
    out.append(back_row("◀️ Orqaga", "bc"))
    return kb(*out)


# ------------------------------------------------------------------ anime
def an_menu(custom: int, rec: int, pop: int) -> InlineKeyboardMarkup:
    return kb(
        [b("➕ Anime qo'shish", "an", "add")],
        [b(f"📚 Qo'shilgan animelar ({custom})", "an", "list", page=1)],
        [b(f"⭐ Tavsiya etilganlar ({rec})", "fa", "list", arg="rec")],
        [b(f"🔥 Mashhur ro'yxati ({pop})", "fa", "list", arg="pop")],
        [home_btn()],
    )


def an_list(rows: list[dict[str, Any]], page: int, pages: int) -> InlineKeyboardMarkup:
    out = [[b(f"🎬 {r['title'][:45]} · #{r['id']}", "an", "view", id=r["id"], page=page)] for r in rows]
    if pages > 1:
        out.append(pager("an", "list", page, pages))
    out.append([b("➕ Qo'shish", "an", "add")])
    out.append(back_row("◀️ Orqaga", "an"))
    return kb(*out)


def an_card(row: dict[str, Any], page: int, is_rec: bool, is_pop: bool) -> InlineKeyboardMarkup:
    i = row["id"]
    e = lambda text, field: b(text, "an", "edit", id=i, arg=field)  # noqa: E731
    return kb(
        [e("✏️ Nomi", "title"), e("🇬🇧 Inglizcha nom", "title_en")],
        [e("📖 Tavsif", "synopsis"), e("🎭 Janrlar", "genres")],
        [e("📺 Turi", "anime_type"), e("🔢 Qismlar", "episodes")],
        [e("📅 Yil", "year"), e("📌 Holat", "status")],
        [e("⭐ Reyting", "score"), e("🖼 Rasm", "photo")],
        [b("✅ Tavsiyadan olish" if is_rec else "⭐ Tavsiyaga qo'shish", "an", "feat", id=i, arg="rec"),
         b("✅ Mashhurdan olish" if is_pop else "🔥 Mashhurga qo'shish", "an", "feat", id=i, arg="pop")],
        [b("🗑 O'chirish", "an", "del", id=i)],
        [b("◀️ Ro'yxat", "an", "list", page=max(page, 1)), home_btn()],
    )


def form_kb(choices: tuple[tuple[str, str], ...], optional: bool, clear_label: str | None
            ) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(choices), 2):
        rows.append([b(label, "an", "ch", arg=val) for val, label in choices[i:i + 2]])
    if optional:
        rows.append([b(clear_label or "⏭ O'tkazib yuborish", "an", "skip")])
    rows.append([b("❌ Bekor qilish", "an", "cancel")])
    return kb(*rows)


def form_confirm() -> InlineKeyboardMarkup:
    return kb([b("✅ Saqlash", "an", "save")], [b("❌ Bekor qilish", "an", "cancel")])


# ------------------------------------------------------------------ tavsiya / mashhur
def fa_list(kind: str, items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = []
    for n, r in enumerate(items, start=1):
        row = [Btn(text=button_label({"title": r["title"], "score": r.get("score")}, n), callback_data="noop")]
        if n > 1:
            row.append(b("⬆️", "fa", "up", id=r["anime_id"], arg=kind))
        row.append(b("🗑", "fa", "rm", id=r["anime_id"], arg=kind))
        rows.append(row)
    rows.append([b("➕ Qo'shish", "fa", "add", arg=kind)])
    rows.append(back_row("◀️ Orqaga", "an"))
    return kb(*rows)


def fa_results(kind: str, items: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [[b(button_label(a, n), "fa", "pick", id=a["mal_id"], arg=kind)]
            for n, a in enumerate(items, start=1)]
    rows.append([b("❌ Bekor qilish", "fa", "list", arg=kind)])
    return kb(*rows)


# ------------------------------------------------------------------ adminlar
def adm_menu(admins: list[AdminInfo], can_add: bool) -> InlineKeyboardMarkup:
    rows = []
    for a in admins:
        crown = "👑" if a.is_super else "🛡"
        rows.append([b(f"{crown} {a.name or UNKNOWN} · {a.user_id}", "adm", "view", id=a.user_id)])
    if can_add:
        rows.append([b("➕ Admin qo'shish", "adm", "add")])
    rows.append([home_btn()])
    return kb(*rows)


def adm_card(target: AdminInfo, viewer: AdminInfo, can_edit: bool,
             grantable: set[str]) -> InlineKeyboardMarkup:
    rows = []
    if can_edit and not target.is_super:
        for perm, label in PERMS.items():
            if perm not in grantable and perm not in target.perms:
                continue
            on = perm in target.perms
            rows.append([b(f"{'✅' if on else '▫️'} {label}", "adm", "tog", id=target.user_id, arg=perm)])
        rows.append([b("🗑 Adminlikdan olib tashlash", "adm", "rm", id=target.user_id)])
    rows.append(back_row("◀️ Adminlar", "adm"))
    return kb(*rows)


# ------------------------------------------------------------------ tarix
def log_page(page: int, pages: int, arg: str) -> InlineKeyboardMarkup:
    rows = [[b(("• " if arg == k else "") + v, "log", "list", page=1, arg=k)
             for k, v in (("all", "Hammasi"), ("me", "Mening harakatlarim"))]]
    if pages > 1:
        rows.append(pager("log", "list", page, pages, arg))
    rows.append([home_btn()])
    return kb(*rows)

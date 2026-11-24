"""⚙️ Adminlarni boshqarish: qo'shish, huquqlar, olib tashlash."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks_admin import AdmCB
from bot.keyboards_admin import adm_card, adm_menu, b, back_row, confirm_kb, kb
from bot.services.access import ALL_PERMS, PERMS, AccessService, AdminInfo
from bot.services.repo import Repo
from bot.states import AdminSG
from bot.utils import timefmt
from bot.utils.text import esc

from .common import guard_router, log_action, mention, notify_user, show

router = Router(name="admin_admins")
guard_router(router, "admins")

SUPER_NOTE = "🔒 <i>Super Admin huquqlarini hech kim o'zgartira olmaydi.</i>"


def grantable(viewer: AdminInfo) -> set[str]:
    """Super Admin hammasini bera oladi; oddiy admin — o'zidagi huquqlarni ('admins' dan tashqari)."""
    return set(ALL_PERMS) if viewer.is_super else set(viewer.perms) - {"admins"}


def can_edit(viewer: AdminInfo, target: AdminInfo) -> str | None:
    """None — mumkin, aks holda rad etish sababi."""
    if target.is_super:
        return "Super Admin huquqlarini o'zgartirib bo'lmaydi."
    if target.user_id == viewer.user_id:
        return "O'z huquqlaringizni o'zgartirib bo'lmaydi."
    if not viewer.is_super and "admins" in target.perms:
        return "Adminlarni boshqarish huquqiga ega adminni faqat Super Admin o'zgartira oladi."
    return None


async def admin_text(target: AdminInfo, repo: Repo) -> str:
    row = await repo.admins.get(target.user_id)
    role = "👑 Super Admin" if target.is_super else "🛡 Admin"
    perms = "\n".join(f"  {'✅' if target.can(p) else '▫️'} {label}" for p, label in PERMS.items())
    added = timefmt.fmt_dt(row["added_at"]) if row else "—"
    text = (f"{role}\n\n{mention(target.name, target.user_id, target.username)}\n"
            f"📅 Qo'shilgan: {added}\n\n<b>Huquqlar:</b>\n{perms}")
    if target.is_super:
        text += f"\n\n{SUPER_NOTE}"
    return text


async def render_admin(event: Message | CallbackQuery, target: AdminInfo, viewer: AdminInfo,
                       repo: Repo) -> None:
    editable = can_edit(viewer, target) is None
    await show(event, await admin_text(target, repo), adm_card(target, viewer, editable, grantable(viewer)))


@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "menu")))
async def adm_home(cb: CallbackQuery, access: AccessService, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    admins = access.admins()
    await show(cb, f"⚙️ <b>Adminlar</b> — {len(admins)} ta\n\n👑 Super Admin · 🛡 Admin\n"
                   "Admin ustiga bosib huquqlarini ko'ring yoki o'zgartiring.", adm_menu(admins, True))


@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "view")))
async def adm_view(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, access: AccessService,
                   repo: Repo) -> None:
    target = access.get(callback_data.id)
    if not target:
        await cb.answer("Admin topilmadi", show_alert=True)
        return
    await cb.answer()
    await render_admin(cb, target, admin, repo)


# ------------------------------------------------------------------ qo'shish
@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "add")))
async def add_start(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.clear()
    await state.set_state(AdminSG.target)
    await show(cb, "➕ <b>Admin qo'shish</b>\n\nYangi adminning <b>Telegram ID</b> yoki <b>@username</b> ini yuboring.\n"
                   "⚠️ U botdan kamida bir marta foydalangan bo'lishi kerak (ID ni /id buyrug'i ko'rsatadi).\n\n"
                   "Bekor qilish: /cancel", kb([b("❌ Bekor qilish", "adm")]))


@router.message(AdminSG.target, F.text, ~F.text.startswith("/"))
async def add_target(message: Message, state: FSMContext, repo: Repo, access: AccessService) -> None:
    u = await repo.users.find(message.text)
    if not u:
        await message.answer("😕 Foydalanuvchi topilmadi. U avval botga /start yuborishi kerak.\n"
                             "Boshqa ID/@username yuboring yoki /cancel.")
        return
    if access.is_admin(u["user_id"]):
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon admin.")
        return
    await state.clear()
    await message.answer(
        f"➕ <b>Admin qo'shishni tasdiqlang</b>\n\n{mention(u['name'], u['user_id'], u.get('username'))}\n\n"
        "Dastlab faqat «📊 Statistika» huquqi beriladi; keyin huquqlarni o'zgartirishingiz mumkin.",
        reply_markup=confirm_kb("adm", "add_yes", "menu", id=u["user_id"], yes_text="✅ Ha, qo'shish"))


@router.message(AdminSG.target)
async def add_wrong(message: Message) -> None:
    await message.answer("✏️ ID yoki @username ni matn ko'rinishida yuboring (yoki /cancel).")


@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "add_yes")))
async def add_do(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, access: AccessService,
                 repo: Repo) -> None:
    u = await repo.users.get(callback_data.id)
    if not u:
        await cb.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    if not await access.add_admin(u["user_id"], u["name"], u.get("username"), admin.user_id):
        await cb.answer("Bu foydalanuvchi allaqachon admin.", show_alert=True)
        return
    await log_action(repo, admin, "admin_add", f"{u['name']} ({u['user_id']})")
    await notify_user(cb.bot, u["user_id"], "🛡 Siz botga <b>admin</b> etib tayinlandingiz. /admin — panelni ochish.")
    await cb.answer("✅ Admin qo'shildi")
    await render_admin(cb, access.get(u["user_id"]), admin, repo)


# ------------------------------------------------------------------ huquqlar
@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "tog")))
async def toggle_perm(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, access: AccessService,
                      repo: Repo) -> None:
    target = access.get(callback_data.id)
    perm = callback_data.arg
    if not target or perm not in ALL_PERMS:
        await cb.answer("Topilmadi", show_alert=True)
        return
    if (why := can_edit(admin, target)):
        await cb.answer(why, show_alert=True)
        return
    if perm not in grantable(admin):
        await cb.answer("Bu huquqni berish yoki olish uchun sizda ruxsat yo'q.", show_alert=True)
        return
    perms = set(target.perms)
    granted = perm not in perms
    (perms.add if granted else perms.discard)(perm)
    await access.set_perms(target.user_id, frozenset(perms))
    await log_action(repo, admin, "admin_perms",
                     f"{target.name} ({target.user_id}): {'+' if granted else '−'}{perm}")
    await cb.answer("✅ Berildi" if granted else "➖ Olib tashlandi")
    await render_admin(cb, access.get(target.user_id), admin, repo)


# ------------------------------------------------------------------ olib tashlash
@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "rm")))
async def remove_ask(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, access: AccessService,
                     repo: Repo) -> None:
    target = access.get(callback_data.id)
    if not target:
        await cb.answer("Admin topilmadi", show_alert=True)
        return
    if (why := can_edit(admin, target)):
        await cb.answer(why, show_alert=True)
        return
    await cb.answer()
    await show(cb, f"🗑 <b>Adminlikdan olib tashlashni tasdiqlang</b>\n\n"
                   f"{mention(target.name, target.user_id, target.username)}",
               confirm_kb("adm", "rm_yes", "view", id=target.user_id, yes_text="🗑 Ha, olib tashlash"))


@router.callback_query(AdmCB.filter((F.sec == "adm") & (F.act == "rm_yes")))
async def remove_do(cb: CallbackQuery, callback_data: AdmCB, admin: AdminInfo, access: AccessService,
                    repo: Repo) -> None:
    target = access.get(callback_data.id)
    if not target:
        await cb.answer("Admin topilmadi", show_alert=True)
        return
    if (why := can_edit(admin, target)):  # amal oldidan qayta tekshiruv
        await cb.answer(why, show_alert=True)
        return
    if not await access.remove_admin(target.user_id):
        await cb.answer("Olib tashlab bo'lmadi", show_alert=True)
        return
    await log_action(repo, admin, "admin_remove", f"{target.name} ({target.user_id})")
    await notify_user(cb.bot, target.user_id, "ℹ️ Sizning admin huquqlaringiz olib tashlandi.")
    await cb.answer("🗑 Olib tashlandi")
    admins = access.admins()
    await show(cb, f"⚙️ <b>Adminlar</b> — {len(admins)} ta", adm_menu(admins, True))

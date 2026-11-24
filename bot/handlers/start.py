from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards import BTN_HELP, main_menu
from bot.services.access import AccessService
from bot.utils.text import esc

router = Router(name="start")

WELCOME = (
    "👋 Salom, <b>{name}</b>!\n\n"
    "🎌 Men — anime botman. Millionlab anime haqida ma'lumot topib beraman.\n\n"
    "Anime nomini yozing yoki pastdagi tugmalardan foydalaning 👇"
)

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "🔍 <b>Qidirish</b> — anime nomini yozing (masalan: <code>Naruto</code>)\n"
    "🔥 <b>Mashhur</b> — eng ommabop animelar\n"
    "🏆 <b>Top reyting</b> — eng yuqori baholanganlar\n"
    "🎭 <b>Janrlar</b> — janr bo'yicha tanlash\n"
    "🎲 <b>Tavsiya</b> — tasodifiy yoki sevimlilaringizga o'xshash\n"
    "⭐ <b>Sevimlilar</b> — saqlangan animelaringiz\n\n"
    "💡 Eng yaxshi natija uchun nomni inglizcha yoki yapon (romaji) yozuvida kiriting.\n\n"
    "👨‍💻 Admin: @{admin}"
)


@router.message(CommandStart())
async def cmd_start(message: Message, access: AccessService) -> None:
    name = esc(message.from_user.first_name if message.from_user else "do'st")
    is_admin = bool(message.from_user and access.is_admin(message.from_user.id))
    await message.answer(WELCOME.format(name=name), reply_markup=main_menu(is_admin))


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message, admin_username: str, access: AccessService) -> None:
    is_admin = bool(message.from_user and access.is_admin(message.from_user.id))
    await message.answer(HELP.format(admin=admin_username), reply_markup=main_menu(is_admin))

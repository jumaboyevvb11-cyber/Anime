"""Nom bo'yicha qidirish. Bu router eng oxirida: har qanday oddiy matn qidiruv hisoblanadi."""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.keyboards import BTN_SEARCH, anime_list
from bot.services.jikan import JikanClient
from bot.services.repo import Repo
from bot.utils.text import esc

router = Router(name="search")

PROMPT = "🔍 Anime nomini yozing.\nMasalan: <code>Attack on Titan</code>"


async def run_search(message: Message, query: str, jikan: JikanClient, repo: Repo) -> None:
    query = query.strip()
    if len(query) < 2:
        await message.answer("✏️ Kamida 2 ta belgi kiriting.")
        return
    query = query[:100]
    await message.bot.send_chat_action(message.chat.id, "typing")
    items = await jikan.search(query)
    if message.from_user:
        repo.track_search(message.from_user.id, query, len(items))  # statistika (orqa fonda)
    if not items:
        await message.answer(
            f"😕 <b>«{esc(query)}»</b> bo'yicha hech narsa topilmadi.\n"
            "Nomni inglizcha yoki romaji yozuvida qayta urinib ko'ring."
        )
        return
    await message.answer(
        f"🔍 <b>«{esc(query)}»</b> bo'yicha natijalar:\n👇 Birini tanlang:",
        reply_markup=anime_list(items),
    )


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, jikan: JikanClient,
                     repo: Repo) -> None:
    if not command.args:
        await message.answer(PROMPT)
        return
    await run_search(message, command.args, jikan, repo)


@router.message(F.text == BTN_SEARCH)
async def search_prompt(message: Message) -> None:
    await message.answer(PROMPT)


@router.message(F.text, ~F.text.startswith("/"))
async def search_text(message: Message, jikan: JikanClient, repo: Repo) -> None:
    await run_search(message, message.text, jikan, repo)

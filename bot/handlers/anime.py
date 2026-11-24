"""Anime kartochkasi, tasodifiy va o'xshash animelar, tavsiyalar."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.callbacks import CB_RANDOM, CB_REC_FAV, AnimeCB, SimCB
from bot.keyboards import BTN_RECOMMEND, anime_list, recommend_menu
from bot.services.jikan import JikanClient
from bot.services.repo import Repo
from bot.services.storage import BaseStorage
from bot.utils.messages import send_anime

router = Router(name="anime")


@router.callback_query(AnimeCB.filter())
async def open_anime(cb: CallbackQuery, callback_data: AnimeCB,
                     jikan: JikanClient, storage: BaseStorage, repo: Repo) -> None:
    await cb.answer()
    anime = await jikan.anime(callback_data.id)
    repo.track_view(anime)  # statistika (orqa fonda)
    await send_anime(cb.bot, cb.from_user.id, cb.from_user.id, anime, storage)


@router.message(Command("recommend"))
@router.message(F.text == BTN_RECOMMEND)
async def recommend_menu_msg(message: Message, repo: Repo) -> None:
    await message.answer("🎲 <b>Tavsiyalar</b>\nQanday tavsiya kerak?",
                         reply_markup=recommend_menu(bool(repo.catalog.featured("rec"))))


@router.callback_query(F.data == CB_RANDOM)
async def random_anime(cb: CallbackQuery, jikan: JikanClient, storage: BaseStorage,
                       repo: Repo) -> None:
    await cb.answer("🎲 Qidirilmoqda...")
    anime = await jikan.random()
    repo.track_view(anime)
    await send_anime(cb.bot, cb.from_user.id, cb.from_user.id, anime, storage)


@router.callback_query(SimCB.filter())
async def similar(cb: CallbackQuery, callback_data: SimCB, jikan: JikanClient) -> None:
    await cb.answer()
    items = await jikan.similar(callback_data.id)
    if not items:
        await cb.bot.send_message(cb.from_user.id, "😕 Bu anime uchun tavsiyalar topilmadi.")
        return
    await cb.bot.send_message(
        cb.from_user.id, "🔁 <b>O'xshash animelar:</b>", reply_markup=anime_list(items)
    )


@router.callback_query(F.data == CB_REC_FAV)
async def recommend_from_favorites(cb: CallbackQuery, jikan: JikanClient,
                                   storage: BaseStorage) -> None:
    uid = cb.from_user.id
    favs = await storage.list(uid, limit=3, offset=0)
    if not favs:
        await cb.answer("Avval sevimlilarga anime qo'shing ⭐", show_alert=True)
        return
    await cb.answer("🎯 Tanlanmoqda...")
    owned = {f["mal_id"] for f in favs}
    pool: dict[int, dict] = {}
    for fav in favs:
        for entry in await jikan.similar(fav["mal_id"]):
            if entry["mal_id"] not in owned:
                pool.setdefault(entry["mal_id"], entry)
    items = list(pool.values())[:10]
    if not items:
        await cb.bot.send_message(uid, "😕 Hozircha mos tavsiya topilmadi.")
        return
    await cb.bot.send_message(
        uid, "🎯 <b>Sevimlilaringizga asoslangan tavsiyalar:</b>",
        reply_markup=anime_list(items),
    )

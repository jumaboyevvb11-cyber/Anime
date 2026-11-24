import asyncio
import pytest
from tests.sim import World


def run(coro):
    return asyncio.run(coro)


def test_dispatcher_wiring_and_storage_collision(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        assert "storage" in w.dp.workflow_data
        from aiogram import Dispatcher
        with pytest.raises(TypeError):   # asl kod: Dispatcher(storage=<sevimlilar saqlagichi>) shu xatoni berardi
            Dispatcher(storage=w.storage)
        assert set(w.dp.resolve_used_update_types()) == {"callback_query", "message"}
    run(go())


def test_regular_user_flows_unchanged(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        u = w.client(100, "ali", "Ali")
        await u.send("/start")
        assert "Salom" in u.text()
        assert w.repo.users.blocked == set()
        assert (await w.repo.users.get(100))["name"] == "Ali"
        await u.send("naruto")
        assert "natijalar" in u.text() and any("Naruto" in b for b in u.buttons())
        await u.press("Naruto")                        # kartochka (rasm + caption)
        assert w.bot.chat_msgs(100)[-1]["photo"] == "IMG_20"
        await u.press("Sevimlilarga qo'shish")
        assert await w.storage.count(100) == 1
        await u.send("⭐ Sevimlilar")
        assert "Sevimli animelaringiz" in u.text()
        await u.send("/top"); assert "Top anime" in u.text()
        await u.send("🔥 Mashhur"); assert "Mashhur" in u.text()
        await u.send("🎭 Janrlar"); await u.press("Jangari"); assert "janri" in u.text()
        await u.send("🎲 Tavsiya"); assert "⭐ Admin tavsiyalari" not in " ".join(u.buttons())
        await u.press("Tasodifiy")
        await u.send("ℹ️ Yordam"); assert "Yordam" in u.text()
        assert "Admin panel" not in str([k.text for row in u.bot.chat_msgs(100)[-1]["markup"].keyboard for k in row]) \
            if hasattr(u.bot.chat_msgs(100)[-1]["markup"], "keyboard") else True
        # statistika yig'ilgan
        assert await w.repo.searches.total() == 1
        assert (await w.repo.searches.top_animes())[0]["title"] == "Naruto"
        assert u.unhandled == 0
    run(go())

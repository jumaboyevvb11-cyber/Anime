import asyncio

import pytest
from bot.services.database import SQLiteDatabase
from bot.services.repo import Repo


@pytest.fixture
def repo():
    r = Repo(SQLiteDatabase(":memory:"))
    asyncio.run(r.start())
    return r


def test_broadcaster_retry_after(repo):
    from aiogram.exceptions import TelegramRetryAfter
    from bot.services.broadcaster import Broadcaster
    from tests.sim import FakeBot

    async def go():
        for i in (1, 2, 3):
            await repo.users.upsert(i, f"U{i}", None)
        bot = FakeBot()
        src = await bot.send_message(9, "salom")
        state = {"n": 0}
        orig = bot.copy_message

        async def flaky(chat_id, **kw):
            if chat_id == 2 and state["n"] == 0:
                state["n"] += 1
                raise TelegramRetryAfter(0)
            return await orig(chat_id, **kw)
        bot.copy_message = flaky
        events = []

        async def notify(job, final): events.append(final)
        b = Broadcaster(bot, repo, per_second=2)
        job = await b.start(9, 9, src.message_id, None, "text", "salom", notify)
        await b._task
        assert (job.sent, job.failed, job.blocked, job.status) == (3, 0, 0, "done")
        assert events[-1] is True
        assert (await b.start(9, 9, src.message_id, None, "text", "x", notify)) is not None  # tugagach yangisi mumkin
        await b._task
    asyncio.run(go())



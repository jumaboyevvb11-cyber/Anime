"""Barcha admin tugmalarini avtomatik bosib chiqish: ishlamaydigan yoki javobsiz tugma bo'lmasligi kerak."""
import asyncio
from collections import deque

from aiogram.types import InlineKeyboardMarkup
from tests.sim import World

DESTRUCTIVE = {"block_yes", "unblock_yes", "del_yes", "rm_yes", "add_yes", "go", "save", "stop", "up"}


def run(coro):
    return asyncio.run(coro)


def all_buttons(c):
    seen = {}
    for rec in c.bot.chat_msgs(c.uid):
        if rec["who"] == "bot" and isinstance(rec["markup"], InlineKeyboardMarkup):
            for row in rec["markup"].inline_keyboard:
                for b in row:
                    if b.callback_data:
                        seen[b.callback_data] = (rec, b)
    return seen


def test_every_admin_button_works(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        s = await w.make_super()
        for i in range(12):                                     # sahifalash uchun foydalanuvchilar
            u = w.client(100 + i, f"u{i}", f"U{i}")
            await u.send("/start"); await u.send("naruto")
        await w.client(100).press("Naruto")
        await w.repo.users.set_blocked(105, True, 1)
        await w.access.add_admin(100, "U0", "u0", 1)
        await w.access.set_perms(100, frozenset({"stats", "users"}))
        for t in ("Anime A", "Anime B"):
            await w.repo.catalog.add({"title": t, "genres": "Drama", "photo": "P1"}, 1)
        await w.repo.catalog.feature_add("rec", -1, "Anime A", None, 1)
        await w.repo.catalog.feature_add("rec", 20, "Naruto", 8.0, 1)
        await w.repo.catalog.feature_add("pop", 1, "Cowboy Bebop", 8.7, 1)
        await w.repo.broadcasts.create(1, "text", "eski", 3)
        for i in range(10):
            await w.repo.logs.add(1, "Juma", "user_block", f"ID {i}")

        visited, queue, presses = set(), deque([[]]), 0
        while queue:
            path = queue.popleft()
            await s.send("/admin")
            ok = True
            for cd in path:
                rec_btn = all_buttons(s).get(cd)
                assert rec_btn, f"Yo'l buzildi: {path} -> {cd}"
                await s.press_btn(*rec_btn); presses += 1
            for cd, (rec, b) in all_buttons(s).items():
                parts = cd.split(":")
                act = parts[2] if parts[0] == "ad" else ""
                if cd in visited or act in DESTRUCTIVE or (parts[0] == "ad" and parts[1] == "fa" and act == "rm"):
                    continue
                # faqat oxirgi ko'rinishdagi tugmalarni (hozirgi xabarlar) olamiz
                last_markup_cds = {x.callback_data for r in [s.bot.chat_msgs(s.uid)[-1]] if r["who"] == "bot"
                                   and isinstance(r["markup"], InlineKeyboardMarkup)
                                   for row in r["markup"].inline_keyboard for x in row}
                if cd not in last_markup_cds:
                    continue
                visited.add(cd)
                queue.append(path + [cd])
        assert s.unhandled == 0
        assert presses > 150, presses
        print("bosilgan tugmalar:", presses, "noyob:", len(visited))
    run(go())

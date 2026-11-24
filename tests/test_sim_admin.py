import asyncio
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from tests.sim import World


def run(coro):
    return asyncio.run(coro)


def test_security_non_admin_blocked(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        u = w.client(100, "hacker", "H")
        await u.send("/start")
        await u.send("/admin")
        assert "faqat adminlar" in u.text()
        await u.send("🛠 Admin panel")
        assert "faqat adminlar" in u.text()
        # soxta callback (tugma yo'q, lekin qo'lda yuborilgan)
        from tests.sim import Client
        from aiogram.types import InlineKeyboardButton
        from bot.callbacks_admin import AdmCB
        for sec, act, arg in [("home", "menu", ""), ("stats", "ov", ""), ("users", "block_yes", ""),
                              ("bc", "go", ""), ("an", "del_yes", ""), ("adm", "add_yes", ""),
                              ("log", "list", ""), ("fa", "rm", "rec")]:
            btn = InlineKeyboardButton(text="x", callback_data=AdmCB(sec=sec, act=act, id=5, arg=arg).pack())
            rec = w.bot._record(100, text="x")
            rec = w.bot.msgs[(100, rec.message_id)]
            await u.press_btn(rec, btn)
            txt, alert = u.alert()
            assert alert and "⛔" in txt, (sec, act, txt)
        assert await w.repo.users.blocked_count() == 0
        # oddiy foydalanuvchi qidiruvi ishlashda davom etadi
        await u.send("naruto")
        assert "natijalar" in u.text()
        # /claim: noto'g'ri kod / username
        await u.send(f"/claim {w.access._code}")
        assert "mos kelmadi" in u.text() and not w.access.is_admin(100)
        await u.send("/id"); assert "100" in u.text()
    run(go())


def test_claim_flow(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        code = w.access._code
        evil = w.client(66, "jumaboyev101_fake", "Evil")
        await evil.send(f"/claim {code}")
        assert not w.access.is_admin(66)
        real = w.client(1, "JumaBoyev101", "Juma")
        await real.send("/start")
        await real.send("/claim BAD")
        assert "mos kelmadi" in real.text()
        await real.send(f"/claim {code}")
        assert w.access.is_super(1)
        assert "Super Admin" in real.text()
        # kod xabari chatdan o'chirilgan
        assert not any(r["who"] == "user" and "/claim" in (r.get("text") or "") for r in w.bot.chat_msgs(1))
        # keyin hech kim claim qila olmaydi, bot jim
        bots = lambda: [r for r in w.bot.chat_msgs(66) if r["who"] == "bot"]
        n = len(bots())
        await evil.send(f"/claim {code}")
        assert len(bots()) == n and not w.access.is_admin(66)
        # super endi /start da admin tugmasi oladi va panelni ocha oladi
        await real.send("/admin")
        assert "Admin panel" in real.text() and "Super Admin" in real.text()
        assert (await w.repo.logs.page(5, 0))[0]["action"] == "super_claim"
    run(go())


def test_stats_all_pages(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        u = w.client(100, "ali", "Ali")
        await u.send("/start"); await u.send("naruto"); await u.press("Naruto")
        await a.send("/admin")
        await a.press("Statistika")
        for label, needle in [("Umumiy", "Jami foydalanuvchilar"), ("Foydalanuvchilar", "Oxirgi 7 kun"),
                              ("Qidiruvlar", "Eng ko'p qidirilganlar"), ("Top animelar", "ko'rilgan"),
                              ("Bot holati", "Botning umumiy holati")]:
            await a.press("◀️ Statistika") if "Statistika" in str(a.buttons()) and label != "Umumiy" else None
            await a.press(label)
            assert needle in a.text(), (label, a.text())
        await a.press("◀️ Statistika")
        await a.press("Qidiruvlar")
        assert "naruto" in a.text()
        for per in ["7 kun", "30 kun", "Bugun"]:
            await a.press(per); assert "Qidiruvlar" in a.text()
        await a.press("Yangilash")
        await a.press("Admin panel")
        assert "Bo'limni tanlang" in a.text()
    run(go())


def test_users_block_unblock_search(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        u = w.client(100, "ali", "Ali")
        await u.send("/start"); await u.send("naruto")
        await a.send("/admin"); await a.press("Foydalanuvchilar")
        await a.press("Barcha foydalanuvchilar")
        assert "Ali" in " ".join(a.buttons())
        await a.press("Ali")
        assert "Qidiruvlar: <b>1" in a.text() and "Faol" in a.text()
        await a.press("Faollik"); assert "naruto" in a.text()
        await a.press("◀️ Foydalanuvchi")
        await a.press("Bloklash"); assert "tasdiqlang" in a.text()
        await a.press("Yo'q")                      # bekor qilish
        assert 100 not in w.repo.users.blocked
        await a.press("Bloklash"); await a.press("Ha, bloklash")
        assert 100 in w.repo.users.blocked and "Bloklangan" in a.text()
        # bloklangan foydalanuvchi botdan foydalana olmaydi
        await u.send("naruto"); assert "bloklangansiz" in u.text()
        await u.send("/start"); assert "bloklangansiz" in u.text()
        from aiogram.types import InlineKeyboardButton
        # tugma bosganda ham
        await u.send("x")
        # admin ro'yxatda bloklanganlar
        await a.press("Ro'yxat"); await a.press("Orqaga")
        await a.press("Bloklanganlar"); assert "Ali" in " ".join(a.buttons())
        await a.press("Ali"); await a.press("Blokdan chiqarish"); await a.press("Ha, chiqarish")
        assert 100 not in w.repo.users.blocked
        assert "blokdan chiqarildingiz" in u.text()
        await u.send("naruto"); assert "natijalar" in u.text()
        # ID bo'yicha qidirish
        await a.send("/admin"); await a.press("Foydalanuvchilar"); await a.press("qidirish")
        await a.send("999"); assert "Topilmadi" in a.text()
        await a.send("@ALI"); assert "Foydalanuvchi" in a.text() and "Ali" in a.text()
        # adminni bloklab bo'lmaydi
        await a.send("/admin"); await a.press("Foydalanuvchilar"); await a.press("qidirish")
        await a.send("1")
        assert "Bloklash" not in " ".join(a.buttons())
        acts = [r["action"] for r in await w.repo.logs.page(10, 0)]
        assert "user_block" in acts and "user_unblock" in acts
    run(go())


def test_broadcast_flow(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        users = [w.client(100 + i, f"u{i}", f"U{i}") for i in range(6)]
        for u in users:
            await u.send("/start")
        w.bot.fail[101] = TelegramForbiddenError("blocked")
        w.bot.fail[102] = TelegramBadRequest("chat not found")
        await a.send("/admin"); await a.press("Xabar yuborish"); await a.press("Yangi xabar")
        await a.photo("PHOTO_X", caption="Aksiya!")
        assert "tugma" in a.text()
        await a.press("Tugma qo'shish")
        await a.send("noto'g'ri"); assert "Format noto'g'ri" in a.text()
        await a.send("Ko'rish | ftp://x"); assert "Format noto'g'ri" in a.text()
        await a.send("Ko'rish | https://t.me/kanal")
        # ko'rib chiqish + tasdiq
        texts = a.recent_texts(3)
        assert any("shunday ko'rinadi" in t for t in texts)
        assert w.bot.chat_msgs(1)[-2]["photo"] == "PHOTO_X" and w.bot.chat_msgs(1)[-2]["markup"] is not None
        await a.press("Hammaga yuborish")
        for _ in range(50):
            await asyncio.sleep(0.05)
            if w.broadcaster.current.status != "running": break
        j = w.broadcaster.current
        assert j.status == "done"
        assert (j.sent, j.blocked, j.failed, j.total) == (4 + 0, 1, 1, 7) or j.total == 7, vars(j)
        assert j.sent == 5 and j.blocked == 1 and j.failed == 1, vars(j)   # a (admin) ham foydalanuvchi
        got = [c for c in w.bot.calls if c[0] == "copy_message" and c[1]["chat_id"] == 103]
        assert len(got) == 1
        rec = [r for r in w.bot.chat_msgs(103) if r.get("copied")][0]
        assert rec["photo"] == "PHOTO_X" and rec["markup"].inline_keyboard[0][0].url == "https://t.me/kanal"
        # yakuniy xabar va bazadagi yozuv
        assert "yakunlandi" in " ".join(a.recent_texts(3))
        row = await w.repo.broadcasts.get(j.id)
        assert row["status"] == "done" and row["sent"] == 5 and row["blocked"] == 1 and row["failed"] == 1
        # botni bloklagan/chat topilmagan foydalanuvchilar keyingi safar chiqarib tashlanadi
        assert set(await w.repo.users.broadcast_ids()) == {1, 100, 103, 104, 105}
        # tarix
        await a.press("Tarix") if "Tarix" in " ".join(a.buttons()) else await a.press("Admin panel")
        await a.send("/admin"); await a.press("Xabar yuborish"); await a.press("Yuborishlar tarixi")
        await a.press("#"); assert "Botni bloklagan: <b>1" in a.text()
    run(go())


def test_broadcast_stop_and_busy(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        for i in range(30):
            await w.client(200 + i, None, f"U{i}").send("/start")
        await a.send("/admin"); await a.press("Xabar yuborish"); await a.press("Yangi xabar")
        await a.send("Salom hammaga")
        await a.press("Tugmasiz")
        await a.press("Hammaga yuborish")
        assert w.broadcaster.busy
        await a.press("To'xtatish")
        for _ in range(100):
            await asyncio.sleep(0.05)
            if not w.broadcaster.busy: break
        assert w.broadcaster.current.status == "cancelled" and w.broadcaster.current.processed < 31
        actions = [r["action"] for r in await w.repo.logs.page(10, 0)]
        assert "broadcast_stop" in actions and "broadcast_end" in actions
    run(go())

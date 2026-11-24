import asyncio
from tests.sim import World


def run(coro):
    return asyncio.run(coro)


async def add_full_anime(a, title="Mening Animem"):
    await a.press("Anime qo'shish")
    await a.send("x")                              # juda qisqa nom
    assert "kamida 2" in a.text()
    await a.send(title)
    await a.send("My Anime")
    await a.send("Qiziqarli <hikoya> & sarguzasht")
    await a.send("Jangari, Drama, jangari")
    await a.press("TV serial")
    await a.send("abc"); assert "Raqam" in a.text()
    await a.send("12")
    await a.send("1800"); assert "gacha" in a.text()
    await a.send("2021")
    await a.press("Tugagan")
    await a.send("11"); assert "gacha" in a.text()
    await a.send("8,5")
    await a.send("matn"); assert "Rasm yuboring" in a.text()
    await a.photo("PHOTO_MY")
    assert w_caption(a).count("Mening") == 1


def w_caption(a):
    return a.bot.chat_msgs(a.uid)[-1].get("caption") or ""


def test_anime_crud_and_user_visibility(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        await a.send("/admin"); await a.press("Anime boshqaruvi")
        await add_full_anime(a)
        assert "✅ Saqlash" in a.buttons()
        await a.press("Saqlash")
        assert w.repo.catalog.count() == 1
        row = w.repo.catalog.get(1)
        assert row["genres"] == "Jangari, Drama" and row["score"] == 8.5 and row["photo"] == "PHOTO_MY"
        last = w.bot.chat_msgs(1)[-1]
        assert last["photo"] == "PHOTO_MY" and "Qisqacha mazmun</b>\n" in last["caption"]
        assert "(inglizcha)" not in last["caption"]
        # tahrirlash: matn, tanlov, tozalash, rasm
        await a.press("Nomi"); await a.send("Yangi Nom")
        assert w.repo.catalog.get(1)["title"] == "Yangi Nom"
        await a.press("Holat"); await a.press("Efirda")
        assert w.repo.catalog.get(1)["status"] == "Currently Airing"
        await a.press("Reyting"); await a.press("tozalash")
        assert w.repo.catalog.get(1)["score"] is None
        await a.press("Rasm"); await a.photo("PHOTO_NEW")
        assert w.repo.catalog.get(1)["photo"] == "PHOTO_NEW"
        await a.press("Qismlar"); await a.press("Bekor qilish")      # bekor -> kartochka
        assert w.repo.catalog.get(1)["episodes"] == 12
        # tavsiya va mashhurga qo'shish
        await a.press("Tavsiyaga qo'shish"); await a.press("Mashhurga qo'shish")
        assert w.repo.catalog.is_featured("rec", -1) and w.repo.catalog.is_featured("pop", -1)
        # foydalanuvchi tomonida
        u = w.client(100, "ali", "Ali")
        await u.send("/start"); await u.send("yangi nom")
        assert "My Anime" in " ".join(u.buttons())      # mavjud button_label inglizcha nomni afzal ko'radi
        await u.press("My Anime")
        card = w.bot.chat_msgs(100)[-1]
        assert card["photo"] == "PHOTO_NEW" and "Efirda" in card["caption"]
        await u.press("Sevimlilarga qo'shish")
        assert await w.storage.exists(100, -1)
        await u.send("⭐ Sevimlilar"); assert "My Anime" in " ".join(u.buttons())
        await u.press("O'xshash") ; assert "topilmadi" in u.text()
        await u.send("🔥 Mashhur"); assert u.buttons()[0].endswith("Yangi Nom")
        await u.send("🎲 Tavsiya"); await u.press("Admin tavsiyalari")
        assert "Admin tavsiyalari" in u.text() and "Yangi Nom" in " ".join(u.buttons())
        await u.press("Yangi Nom")
        # o'chirish: tasdiq, so'ng hamma joydan yo'qoladi
        await a.press("O'chirish"); assert "tasdiqlang" in a.text()
        await a.press("Yo'q")
        assert w.repo.catalog.count() == 1
        await a.press("O'chirish"); await a.press("Ha, o'chirish")
        assert w.repo.catalog.count() == 0 and w.repo.catalog.featured("rec") == []
        assert not await w.storage.exists(100, -1)
        await u.send("yangi nom"); assert "topilmadi" in u.text()
        acts = [r["action"] for r in await w.repo.logs.page(30, 0)]
        for k in ("anime_add", "anime_edit", "anime_delete", "feature_add"):
            assert k in acts
    run(go())


def test_anime_form_cancel_and_skip(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        await a.send("/admin"); await a.press("Anime boshqaruvi"); await a.press("Anime qo'shish")
        assert "o'tkazib" not in " ".join(a.buttons()).lower()      # nom majburiy
        await a.send("Faqat Nom")
        for _ in range(9):
            await a.press("O'tkazib")
        await a.press("Saqlash")
        row = w.repo.catalog.get(1)
        assert row["title"] == "Faqat Nom" and row["score"] is None and row["photo"] is None
        # rasmsiz kartochka matn sifatida
        assert "photo" not in w.bot.chat_msgs(1)[-1] or not w.bot.chat_msgs(1)[-1].get("photo")
        # bekor qilish va /cancel
        await a.send("/admin"); await a.press("Anime boshqaruvi")
        await a.press("Anime qo'shish"); await a.send("Boshqa"); await a.press("Bekor qilish")
        assert w.repo.catalog.count() == 1
        assert "Anime boshqaruvi" in a.text()
        await a.press("Anime qo'shish"); await a.send("/cancel")
        assert not w.dp.fsm_storage.states
        # sessiya tugagandan keyin eski tugma xavfsiz rad etiladi
        await a.send("/admin"); await a.press("Anime boshqaruvi"); await a.press("Anime qo'shish")
        rec, btn = a.find_button("Bekor")
        w.dp.fsm_storage.states.clear(); w.dp.fsm_storage.data.clear()
        from aiogram.types import InlineKeyboardButton
        from bot.callbacks_admin import AdmCB
        stale = InlineKeyboardButton(text="x", callback_data=AdmCB(sec="an", act="save").pack())
        await a.press_btn(rec, stale)
        assert a.alert()[1] and "Sessiya" in a.alert()[0]


def test_featured_lists(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        a = await w.make_super()
        await a.send("/admin"); await a.press("Anime boshqaruvi")
        await a.press("Tavsiya etilganlar"); assert "bo'sh" in a.text()
        await a.press("Qo'shish"); await a.send("zzzz"); assert "topilmadi" in a.text()
        await a.send("naruto"); await a.press("Naruto")
        assert [r["anime_id"] for r in w.repo.catalog.featured("rec")] == [20]
        await a.press("Qo'shish"); await a.send("https://myanimelist.net/anime/1")
        await a.press("Qo'shish"); await a.send("999"); assert "topilmadi" in a.text().lower()
        await a.send("/cancel")
        await a.send("/admin"); await a.press("Anime boshqaruvi"); await a.press("Tavsiya etilganlar")
        assert [r["anime_id"] for r in w.repo.catalog.featured("rec")] == [20, 1]
        await a.press("Qo'shish"); await a.send("1"); assert "allaqachon" in " ".join(a.recent_texts(3))
        await a.press("⬆️")
        assert [r["anime_id"] for r in w.repo.catalog.featured("rec")] == [1, 20]
        u = w.client(100, "ali", "Ali")
        await u.send("/start"); await u.send("🎲 Tavsiya"); await u.press("Admin tavsiyalari")
        assert "Cowboy" in u.buttons()[0]
        await a.press("🗑")
        assert [r["anime_id"] for r in w.repo.catalog.featured("rec")] == [20]
        # mashhur ro'yxati foydalanuvchi "Mashhur" bo'limida tepada
        await a.press("Orqaga"); await a.press("Mashhur ro'yxati")
        await a.press("Qo'shish"); await a.send("bleach"); await a.press("Bleach")
        await u.send("🔥 Mashhur")
        assert "Bleach" in u.buttons()[0]
        await a.press("🗑")
        await u.send("🔥 Mashhur"); assert "Bleach" not in " ".join(u.buttons())
    run(go())


def test_admin_management(tmp_path):
    async def go():
        w = await World.create(tmp_path)
        s = await w.make_super()
        b = w.client(200, "bobur", "Bobur")
        await b.send("/start")
        await s.send("/admin"); await s.press("Adminlar")
        await s.press("Admin qo'shish")
        await s.send("555"); assert "topilmadi" in s.text()
        await s.send("@bobur"); assert "tasdiqlang" in s.text()
        await s.press("Yo'q")
        assert not w.access.is_admin(200)
        await s.press("Admin qo'shish"); await s.send("200"); await s.press("Ha, qo'shish")
        assert w.access.get(200).perms == {"stats"}
        assert "etib tayinlandingiz" in b.text()
        # huquqlarni boshqarish
        await s.press("Foydalanuvchilar"); await s.press("Xabar yuborish"); await s.press("Anime boshqaruvi")
        assert w.access.get(200).perms == {"stats", "users", "broadcast", "anime"}
        await s.press("Xabar yuborish")
        assert w.access.get(200).perms == {"stats", "users", "anime"}
        # yangi admin: faqat o'ziga ruxsat berilgan bo'limlar
        await b.send("/admin")
        assert "Statistika" in " ".join(b.buttons()) and "Xabar yuborish" not in " ".join(b.buttons())
        assert "Adminlar" not in " ".join(b.buttons())
        from bot.callbacks_admin import AdmCB
        from aiogram.types import InlineKeyboardButton
        for sec, act in [("bc", "new"), ("adm", "menu"), ("log", "list")]:
            btn = InlineKeyboardButton(text="x", callback_data=AdmCB(sec=sec, act=act).pack())
            rec = w.bot.msgs[(200, w.bot._record(200, text="x").message_id)]
            await b.press_btn(rec, btn)
            assert b.alert()[1] and "ruxsat" in b.alert()[0].lower()
        # oddiy admin Super Adminni / o'zini o'zgartira olmaydi, 'admins' huquqini bera olmaydi
        await s.send("/admin"); await s.press("Adminlar")
        await s.press("Statistika")
        assert "stats" not in w.access.get(200).perms
        await s.press("Statistika")
        # super admin kartochkasida tahrirlash tugmalari yo'q
        await s.send("/admin"); await s.press("Adminlar"); await s.press("👑")
        assert not any("Statistika" in t or "olib tashlash" in t for t in s.buttons())
        assert "hech kim o'zgartira olmaydi" in s.text()
        # olib tashlash
        await s.send("/admin"); await s.press("Adminlar"); await s.press("Bobur")
        await s.press("olib tashlash"); await s.press("Ha, olib tashlash")
        assert not w.access.is_admin(200)
        assert "olib tashlandi" in b.text()
        await b.send("/admin"); assert "faqat adminlar" in b.text()
        # tarix
        await s.send("/admin"); await s.press("Harakatlar tarixi")
        assert "Admin qo'shildi" in s.text() and "Admin olib tashlandi" in s.text()
        await s.press("Mening harakatlarim"); assert "Admin harakatlari" in s.text()
        await s.press("Hammasi")
    run(go())


def test_peer_admin_protection(tmp_path):
    async def go():
        w = await World.create(tmp_path, env_super_ids=[1], env_admin_ids=[300, 301])
        s = w.client(1, "boss", "Boss"); await s.send("/start")
        for uid in (300, 301):
            await w.client(uid, f"a{uid}", f"A{uid}").send("/start")
        await w.access.set_perms(300, frozenset({"stats", "admins"}))
        await w.access.set_perms(301, frozenset({"stats", "admins"}))
        a300 = w.client(300)
        await a300.send("/admin"); await a300.press("Adminlar")
        await a300.press("A301")
        assert not any("olib tashlash" in t for t in a300.buttons())     # peer tahrirlanmaydi
        assert w.access.get(1).is_super
        # oddiy admin 'admins' huquqini boshqa adminga bera olmaydi
        await w.access.set_perms(301, frozenset({"stats"}))
        await a300.send("/admin"); await a300.press("Adminlar"); await a300.press("A301")
        assert "Adminlar va tarix" not in " ".join(a300.buttons())
    run(go())

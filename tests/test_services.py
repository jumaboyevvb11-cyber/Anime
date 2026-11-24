import asyncio, pytest
from bot.services.database import SQLiteDatabase
from bot.services.repo import Repo
from bot.services.access import AccessService, ClaimResult, ALL_PERMS
from bot.services.catalog_client import CatalogClient, custom_to_jikan
from bot.services.jikan import JikanNotFound
from bot.utils import timefmt


@pytest.fixture
def repo():
    r = Repo(SQLiteDatabase(":memory:"))
    asyncio.run(r.start())
    return r


def run(c): return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(c)


def test_users_block_and_find(repo):
    async def go():
        await repo.users.upsert(1, "Ali", "ali_u")
        await repo.users.upsert(2, "Vali", None)
        assert (await repo.users.find("@ALI_U"))["user_id"] == 1
        assert (await repo.users.find("2"))["name"] == "Vali"
        assert await repo.users.find("999") is None
        assert await repo.users.set_blocked(1, True, 7)
        assert 1 in repo.users.blocked and await repo.users.count("blk") == 1
        assert await repo.users.broadcast_ids() == [2]
        assert await repo.users.set_blocked(1, False, 7) and 1 not in repo.users.blocked
        await repo.users.mark_bot_blocked([2])
        assert await repo.users.broadcast_ids() == [1]
        await repo.users.upsert(2, "Vali", None)  # qaytsa, bot_blocked tozalanadi
        assert await repo.users.broadcast_ids() == [1, 2]
        assert await repo.users.new_since(timefmt.day_start()) == 2
        assert sum((await repo.users.daily_new(timefmt.now() - 86400 * 7)).values()) == 2
    asyncio.run(go())


def test_searches(repo):
    async def go():
        for t in ["Naruto", " naruto ", "Bleach"]:
            await repo.searches.log(5, t, 3)
        assert await repo.searches.total() == 3
        top = await repo.searches.top_terms(0)
        assert top[0] == {"term": "naruto", "c": 2}
        assert await repo.searches.unique_users_since(0) == 1
        await repo.searches.track_view(10, "A"); await repo.searches.track_view(10, "A")
        assert (await repo.searches.top_animes())[0]["views"] == 2
        assert len(await repo.searches.user_recent(5)) == 3
        assert sum((await repo.searches.daily(0)).values()) == 3
    asyncio.run(go())


def test_catalog_and_featured(repo):
    async def go():
        cid = await repo.catalog.add({"title": "Mening Animem", "genres": "Jangari, Drama",
                                      "score": 8.5, "episodes": 12}, 1)
        assert repo.catalog.search_local("anim mening")[0]["id"] == cid
        await repo.catalog.update(cid, "title_en", "My Anime")
        with pytest.raises(ValueError):
            await repo.catalog.update(cid, "id; DROP", 1)
        assert await repo.catalog.feature_add("pop", -cid, "Mening Animem", 8.5, 1)
        assert not await repo.catalog.feature_add("pop", -cid, "x", 1, 1)
        await repo.catalog.feature_add("pop", 20, "Naruto", 8, 1)
        assert await repo.catalog.feature_move_up("pop", 20)
        assert [r["anime_id"] for r in repo.catalog.featured("pop")] == [20, -cid]
        await repo.catalog.update(cid, "title", "Yangi nom")
        assert repo.catalog.featured("pop")[1]["title"] == "Yangi nom"
        d = custom_to_jikan(repo.catalog.get(cid))
        assert d["mal_id"] == -cid and d["genres"][1]["name"] == "Drama"
        assert await repo.catalog.delete(cid)
        assert [r["anime_id"] for r in repo.catalog.featured("pop")] == [20]
    asyncio.run(go())


def test_catalog_client(repo):
    async def go():
        cid = await repo.catalog.add({"title": "Local Hero"}, 1)
        c = CatalogClient("http://x", 1, repo.catalog)
        async def fake_get(path, params=None, ttl=None):
            if path == "/anime":
                return {"data": [{"mal_id": 5, "title": "Remote", "genres": []}]}
            return {"data": [{"mal_id": 9, "title": "Pop9", "genres": []}], "pagination": {}}
        c._get = fake_get
        res = await c.search("local hero")
        assert [a["mal_id"] for a in res] == [-cid, 5]
        assert (await c.anime(-cid))["title"] == "Local Hero"
        with pytest.raises(JikanNotFound):
            await c.anime(-999)
        assert await c.similar(-cid) == []
        await repo.catalog.feature_add("pop", 77, "Pinned", 9, 1)
        items, _ = await c.top(1, popular=True)
        assert [a["mal_id"] for a in items] == [77, 9]
        items, _ = await c.top(1, popular=False)
        assert [a["mal_id"] for a in items] == [9]
    asyncio.run(go())


def test_access_claim(repo):
    async def go():
        acc = AccessService(repo, "@JumaBoyev101", frozenset(), setup_code=None)
        await acc.load()
        code = acc._code
        assert acc.claim_enabled and code
        assert not acc.is_admin(1)
        # noto'g'ri username, to'g'ri kod
        assert await acc.try_claim(2, "hacker", "H", code) == ClaimResult.WRONG
        # to'g'ri username, noto'g'ri kod
        assert await acc.try_claim(1, "jumaboyev101", "J", "AAAA-BBBB-CCCC") == ClaimResult.WRONG
        # username yo'q
        assert await acc.try_claim(3, None, "N", code) == ClaimResult.WRONG
        assert await acc.try_claim(1, "JUMABOYEV101", "J", code.lower().replace("-", " ")) == ClaimResult.OK
        assert acc.is_super(1) and acc.get(1).can("anything") and not acc.claim_enabled
        assert await acc.try_claim(2, "jumaboyev101", "x", code) == ClaimResult.DISABLED
        # qayta ishga tushganda ID bo'yicha tiklanadi, claim yopiq
        acc2 = AccessService(repo, "jumaboyev101", frozenset())
        await acc2.load()
        assert acc2.is_super(1) and not acc2.claim_enabled and acc2._code is None
        # reset
        acc3 = AccessService(repo, "jumaboyev101", frozenset(), reset_binding=True)
        await acc3.load()
        assert not acc3.is_super(1) and acc3.claim_enabled
    asyncio.run(go())


def test_claim_lockout(repo):
    async def go():
        acc = AccessService(repo, "jumaboyev101", frozenset())
        await acc.load()
        for _ in range(5):
            assert await acc.try_claim(9, "jumaboyev101", "x", "bad") == ClaimResult.WRONG
        assert await acc.try_claim(9, "jumaboyev101", "x", acc._code) == ClaimResult.LOCKED
    asyncio.run(go())


def test_admin_management_and_env(repo):
    async def go():
        acc = AccessService(repo, "u", frozenset({100}), frozenset({200}))
        await acc.load()
        assert acc.is_super(100) and not acc.claim_enabled
        assert acc.get(200).can("stats") and not acc.get(200).can("admins")
        assert await acc.add_admin(300, "A", "a", 100)
        assert not await acc.add_admin(300, "A", "a", 100)
        assert await acc.set_perms(300, frozenset({"users", "bogus"} & ALL_PERMS))
        assert acc.get(300).perms == {"users"}
        assert not await acc.set_perms(100, frozenset())   # super o'zgarmaydi
        assert not await acc.remove_admin(100)
        assert await acc.remove_admin(300) and not acc.is_admin(300)
    asyncio.run(go())


def test_config_ids(monkeypatch):
    import config
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("SUPER_ADMIN_IDS", "1, 2;x,3")
    monkeypatch.setenv("SUPER_ADMIN_SETUP_CODE", "")
    c = config.load_config()
    assert c.super_admin_ids == {1, 2, 3} and c.super_admin_username == "jumaboyev101"
    monkeypatch.setenv("SUPER_ADMIN_SETUP_CODE", "short")
    import pytest
    with pytest.raises(RuntimeError):
        config.load_config()

"""Oflayn simulyator: haqiqiy aiogram o'rnatilmagan muhitda handlerlarni butun zanjir bo'yicha sinash.

Bu soddalashtirilgan aiogram (tests/stubs/aiogram) + soxta Telegram (FakeBot) + soxta Jikan.
Telegram cheklovlari (64 bayt callback, 1024 belgi caption, HTML tahlili, "message is not modified",
rasmli xabarni edit_text qilib bo'lmasligi) taqlid qilinadi.
"""
from __future__ import annotations

import asyncio
import itertools
import re
from typing import Any

from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, PhotoSize, Update, User

ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "a", "tg-spoiler", "blockquote"}


def check_html(text: str) -> None:
    stack = []
    for m in re.finditer(r"<(/?)([a-zA-Z-]+)([^>]*)>|<|&(?!(?:amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)", text):
        tok = m.group(0)
        if tok == "<" or tok == "&" or m.group(2) is None:
            raise TelegramBadRequest(f"can't parse entities: bare {tok!r} in {text[:80]!r}")
        closing, tag = m.group(1), m.group(2).lower()
        if tag not in ALLOWED_TAGS:
            raise TelegramBadRequest(f"can't parse entities: unsupported tag {tag}")
        if closing:
            if not stack or stack.pop() != tag:
                raise TelegramBadRequest(f"can't parse entities: unbalanced </{tag}>")
        else:
            stack.append(tag)
    if stack:
        raise TelegramBadRequest(f"can't parse entities: unclosed {stack}")


class FakeBot:
    id = 1

    def __init__(self) -> None:
        self._ids = itertools.count(1000)
        self.msgs: dict[tuple[int, int], dict] = {}
        self.chat_log: dict[int, list[int]] = {}
        self.fail: dict[int, Any] = {}      # chat_id -> Exception (yoki callable) copy/send uchun
        self.answers: list[tuple[str, str | None, bool]] = []
        self.calls: list[tuple[str, dict]] = []
        self.session = self

    async def close(self): ...

    # ---- ichki ----
    def _record(self, chat_id: int, **rec) -> Message:
        mid = next(self._ids)
        self.msgs[(chat_id, mid)] = {"chat": chat_id, "id": mid, "who": "bot", "markup": None, **rec}
        self.chat_log.setdefault(chat_id, []).append(mid)
        return self._msg(chat_id, mid)

    def _msg(self, chat_id: int, mid: int) -> Message:
        r = self.msgs[(chat_id, mid)]
        photo = [PhotoSize(r["photo"])] if r.get("photo") else None
        return Message(message_id=mid, chat=Chat(chat_id), text=r.get("text"), caption=r.get("caption"),
                       photo=photo, bot=self)

    def _maybe_fail(self, chat_id: int) -> None:
        exc = self.fail.get(chat_id)
        if exc is not None:
            raise (exc() if callable(exc) and not isinstance(exc, Exception) else exc)

    @staticmethod
    def _check_markup(m):
        assert m is None or isinstance(m, InlineKeyboardMarkup) or hasattr(m, "keyboard"), m

    # ---- Bot API ----
    async def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.calls.append(("send_message", {"chat_id": chat_id, "text": text}))
        self._maybe_fail(chat_id)
        if not text or len(text) > 4096:
            raise TelegramBadRequest("message text is empty or too long")
        check_html(text)
        self._check_markup(reply_markup)
        return self._record(chat_id, text=text, markup=reply_markup)

    async def send_photo(self, chat_id, photo, caption=None, reply_markup=None, **kw):
        self.calls.append(("send_photo", {"chat_id": chat_id, "photo": photo}))
        self._maybe_fail(chat_id)
        if not isinstance(photo, str) or photo.startswith("BAD"):
            raise TelegramBadRequest("wrong file identifier")
        if caption and len(caption) > 1024:
            raise TelegramBadRequest(f"message caption is too long ({len(caption)})")
        if caption:
            check_html(caption)
        return self._record(chat_id, photo=photo, caption=caption, markup=reply_markup)

    async def edit_message_text(self, text, chat_id=None, message_id=None, reply_markup=None, **kw):
        r = self.msgs.get((chat_id, message_id))
        if r is None:
            raise TelegramBadRequest("message to edit not found")
        if r.get("photo"):
            raise TelegramBadRequest("there is no text in the message to edit")
        check_html(text)
        if r["text"] == text and (r["markup"] == reply_markup or (r["markup"] is None) == (reply_markup is None)
                                  and r["markup"] == reply_markup):
            raise TelegramBadRequest("message is not modified")
        r["text"], r["markup"] = text, reply_markup
        return True

    async def edit_message_reply_markup(self, chat_id=None, message_id=None, reply_markup=None, **kw):
        r = self.msgs.get((chat_id, message_id))
        if r is None:
            raise TelegramBadRequest("message to edit not found")
        if r["markup"] == reply_markup:
            raise TelegramBadRequest("message is not modified")
        r["markup"] = reply_markup
        return True

    async def delete_message(self, chat_id, message_id):
        if (chat_id, message_id) not in self.msgs:
            raise TelegramBadRequest("message to delete not found")
        del self.msgs[(chat_id, message_id)]
        self.chat_log[chat_id].remove(message_id)
        return True

    async def copy_message(self, chat_id, from_chat_id, message_id, reply_markup=None, **kw):
        self.calls.append(("copy_message", {"chat_id": chat_id}))
        self._maybe_fail(chat_id)
        src = self.msgs.get((from_chat_id, message_id))
        if src is None:
            raise TelegramBadRequest("message to copy not found")
        return self._record(chat_id, text=src.get("text"), photo=src.get("photo"),
                            caption=src.get("caption"), markup=reply_markup, copied=True)

    async def answer_callback_query(self, cid, text=None, show_alert=False, **kw):
        self.answers.append((cid, text, show_alert))
        return True

    async def send_chat_action(self, *a, **k): return True
    async def set_my_commands(self, *a, **k): return True
    async def delete_webhook(self, *a, **k): return True

    # ---- yordamchilar ----
    def chat_msgs(self, chat_id: int) -> list[dict]:
        return [self.msgs[(chat_id, m)] for m in self.chat_log.get(chat_id, [])]


class Client:
    """Bitta foydalanuvchi nomidan yozish va tugma bosish."""

    def __init__(self, world: "World", uid: int, username: str | None, name: str = "User") -> None:
        self.w, self.uid = world, uid
        self.user = User(id=uid, first_name=name, username=username)
        self._upd = itertools.count(1)
        self.unhandled = 0

    @property
    def bot(self) -> FakeBot:
        return self.w.bot

    def _user_msg(self, **rec) -> Message:
        mid = next(self.bot._ids)
        self.bot.msgs[(self.uid, mid)] = {"chat": self.uid, "id": mid, "who": "user", "markup": None, **rec}
        self.bot.chat_log.setdefault(self.uid, []).append(mid)
        m = self.bot._msg(self.uid, mid)
        m.from_user = self.user
        return m

    async def _feed(self, update: Update) -> bool:
        handled = await self.w.dp.feed_update(self.bot, update)
        await self.w.settle()
        if not handled:
            self.unhandled += 1
        return handled

    async def send(self, text: str) -> bool:
        return await self._feed(Update(next(self._upd), message=self._user_msg(text=text)))

    async def photo(self, file_id: str = "PHOTO_OK", caption: str | None = None) -> bool:
        return await self._feed(Update(next(self._upd), message=self._user_msg(photo=file_id, caption=caption)))

    def find_button(self, part: str):
        for rec in reversed(self.bot.chat_msgs(self.uid)):
            if rec["who"] == "bot" and isinstance(rec["markup"], InlineKeyboardMarkup):
                for row in rec["markup"].inline_keyboard:
                    for b in row:
                        if part in b.text and b.callback_data:
                            return rec, b
        return None, None

    async def press(self, part: str, expect_handled: bool = True) -> bool:
        rec, btn = self.find_button(part)
        assert btn is not None, f"Tugma topilmadi: {part!r}. Mavjud: {self.buttons()}"
        return await self.press_btn(rec, btn, expect_handled)

    async def press_btn(self, rec, btn, expect_handled: bool = True) -> bool:
        msg = self.bot._msg(rec["chat"], rec["id"])
        cb = CallbackQuery(id=f"cb{next(self.bot._ids)}", from_user=self.user, message=msg,
                           data=btn.callback_data, bot=self.bot)
        handled = await self._feed(Update(next(self._upd), callback_query=cb))
        if expect_handled:
            assert handled, f"Tugma ishlamadi (handler yo'q): {btn.text!r} -> {btn.callback_data!r}"
            assert any(a[0] == cb.id for a in self.bot.answers), \
                f"Callback javobsiz qoldi (spinner): {btn.text!r} -> {btn.callback_data!r}"
        return handled

    def last(self) -> dict:
        return [r for r in self.bot.chat_msgs(self.uid) if r["who"] == "bot"][-1]

    def text(self) -> str:
        r = self.last()
        return (r.get("text") or r.get("caption") or "")

    def recent_texts(self, n: int = 5) -> list[str]:
        return [(r.get("text") or r.get("caption") or "") for r in self.bot.chat_msgs(self.uid)
                if r["who"] == "bot"][-n:]

    def buttons(self) -> list[str]:
        for rec in reversed(self.bot.chat_msgs(self.uid)):
            if rec["who"] == "bot" and isinstance(rec["markup"], InlineKeyboardMarkup):
                return [b.text for row in rec["markup"].inline_keyboard for b in row]
        return []

    def alert(self) -> tuple[str | None, bool]:
        a = self.bot.answers[-1]
        return a[1], a[2]


ANIMES = {
    1: {"mal_id": 1, "title": "Cowboy Bebop", "title_english": "Cowboy Bebop", "score": 8.75,
        "synopsis": "In 2071 <bounty> hunters & more.", "type": "TV", "episodes": 26, "status": "Finished Airing",
        "genres": [{"name": "Action"}], "studios": [{"name": "Sunrise"}], "rank": 45, "popularity": 43,
        "images": {"jpg": {"large_image_url": "IMG_1"}}, "url": "https://myanimelist.net/anime/1",
        "rating": "R - 17+"},
    20: {"mal_id": 20, "title": "Naruto", "title_english": "Naruto", "score": 8.0, "synopsis": "Ninja.",
         "type": "TV", "episodes": 220, "status": "Finished Airing", "genres": [{"name": "Action"}],
         "studios": [], "images": {"jpg": {"large_image_url": "IMG_20"}}, "url": "https://myanimelist.net/anime/20"},
    30: {"mal_id": 30, "title": "Bleach", "score": 7.9, "genres": [], "studios": [], "images": {}},
}


def fake_get_factory():
    async def fake_get(path, params=None, ttl=None):
        params = params or {}
        if path == "/anime":
            q = str(params.get("q", "")).lower()
            data = [a for a in ANIMES.values() if q in a["title"].lower()]
            return {"data": data, "pagination": {"has_next_page": False}}
        if path.startswith("/anime/") and path.endswith("/recommendations"):
            return {"data": [{"entry": {"mal_id": 30, "title": "Bleach"}}]}
        if path.startswith("/anime/"):
            from bot.services.jikan import JikanNotFound
            aid = int(path.split("/")[2])
            if aid not in ANIMES:
                raise JikanNotFound()
            return {"data": ANIMES[aid]}
        if path == "/top/anime":
            return {"data": [ANIMES[1], ANIMES[20]], "pagination": {"has_next_page": False}}
        if path == "/genres/anime":
            return {"data": [{"mal_id": 1, "name": "Action"}]}
        if path == "/random/anime":
            return {"data": ANIMES[20]}
        raise AssertionError(f"kutilmagan Jikan so'rovi: {path}")
    return fake_get


class World:
    @classmethod
    async def create(cls, tmp_path, super_username="jumaboyev101", env_super_ids=(), env_admin_ids=(),
                     setup_code=None) -> "World":
        import importlib
        import sys
        # routerlar modul darajasida bitta marta yaratiladi — har bir sinov uchun yangidan yuklaymiz
        for name in [n for n in sys.modules if n == "main" or n.startswith("bot.handlers")]:
            del sys.modules[name]
        app = importlib.import_module("main")
        from bot.services.access import AccessService
        from bot.services.broadcaster import Broadcaster
        from bot.services.catalog_client import CatalogClient
        from bot.services.database import SQLiteDatabase
        from bot.services.repo import Repo
        from bot.services.stats import StatsService
        from bot.services.storage import JsonStorage

        self = cls()
        self.repo = Repo(SQLiteDatabase(":memory:"))
        await self.repo.start()
        self.access = AccessService(self.repo, super_username, frozenset(env_super_ids),
                                    frozenset(env_admin_ids), setup_code)
        await self.access.load()
        self.storage = JsonStorage(str(tmp_path / "fav.json"))
        await self.storage.init()
        self.jikan = CatalogClient("http://x", 600, self.repo.catalog)
        self.jikan._get = fake_get_factory()
        self.bot = FakeBot()
        self.stats = StatsService(self.repo, self.storage, self.access, self.jikan, "SQLite (test)")
        self.broadcaster = Broadcaster(self.bot, self.repo, per_second=5)
        self.dp = app.build_dispatcher(
            jikan=self.jikan, storage=self.storage, admin_username="jumaboyev101", repo=self.repo,
            access=self.access, stats=self.stats, broadcaster=self.broadcaster, started_at=0.0)
        self.clients: dict[int, Client] = {}
        return self

    def client(self, uid: int, username: str | None = None, name: str = "User") -> Client:
        if uid not in self.clients:
            self.clients[uid] = Client(self, uid, username, name)
        return self.clients[uid]

    async def settle(self) -> None:
        for _ in range(5):
            await asyncio.sleep(0)
            if self.repo._tasks:
                await asyncio.gather(*list(self.repo._tasks), return_exceptions=True)

    async def make_super(self, uid: int = 1, username: str = "jumaboyev101") -> Client:
        c = self.client(uid, username, "Juma")
        await c.send("/start")
        await c.send(f"/claim {self.access._code}")
        assert self.access.is_super(uid)
        return c

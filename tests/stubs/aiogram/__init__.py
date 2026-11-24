"""aiogram 3 ning SINOV uchun soddalashtirilgan nusxasi. Haqiqiy aiogram o'rnatilgan bo'lsa ishlatilmaydi."""
__version__ = "3.13-sim"
import inspect
import re
from typing import Any

from .exceptions import TelegramBadRequest, TelegramForbiddenError
from .fsm.context import FSMContext
from .fsm.state import State
from .fsm.storage.base import BaseStorage
from .fsm.storage.memory import MemoryStorage
from .types import (CallbackQuery, Chat, ErrorEvent, InlineKeyboardMarkup, Message, Update,
                    User)

UNHANDLED = object()


class _Reject(Exception): ...


class MagicFilter:
    def __init__(self, fn=None): self.fn = fn or (lambda o: o)
    def __getattr__(self, name):
        if name.startswith("_"): raise AttributeError(name)
        prev = self.fn
        def fn(o):
            v = prev(o)
            if v is None: raise _Reject
            return getattr(v, name, None)
        return MagicFilter(fn)
    def _derive(self, op):
        prev = self.fn
        return MagicFilter(lambda o: op(prev(o)))
    def __eq__(self, other): return self._derive(lambda v: v == other)
    def __hash__(self): return id(self)
    def startswith(self, p):
        def op(v):
            if not isinstance(v, str): raise _Reject
            return v.startswith(p)
        return self._derive(op)
    def in_(self, coll): return self._derive(lambda v: v in coll)
    def __and__(self, other):
        a, b = self.fn, other.fn
        return MagicFilter(lambda o: bool(a(o)) and bool(b(o)))
    def __or__(self, other):
        a, b = self.fn, other.fn
        def fn(o):
            try:
                if a(o): return True
            except _Reject: pass
            return bool(b(o))
        return MagicFilter(fn)
    def __invert__(self):
        prev = self.fn
        return MagicFilter(lambda o: not prev(o))
    def __call__(self, obj):
        try: return bool(self.fn(obj))
        except _Reject: return False


F = MagicFilter()


class BaseMiddleware:
    async def __call__(self, handler, event, data): raise NotImplementedError


class _MW:
    def __init__(self): self.items = []
    def __call__(self, mw): self.items.append(mw); return mw
    register = __call__


class Observer:
    def __init__(self, router, name):
        self.router, self.name, self.handlers = router, name, []
        self.middleware, self.outer_middleware = _MW(), _MW()
    def __call__(self, *filters, flags=None):
        def deco(cb):
            self.handlers.append((cb, filters)); return cb
        return deco

    async def _wrap(self, mws, final, event, data):
        async def call(i, ev, d):
            if i == len(mws): return await final(ev, d)
            return await mws[i](lambda e, dd: call(i + 1, e, dd), ev, d)
        return await call(0, event, data)

    def _inner(self):
        chain, r = [], self.router
        while r: chain.append(r); r = r.parent
        mws = []
        for r in reversed(chain):
            obs = r.observers.get(self.name)
            if obs: mws.extend(obs.middleware.items)
        return mws

    async def trigger(self, event, data):
        for cb, filters in self.handlers:
            extra, ok = {}, True
            for f in filters:
                if isinstance(f, State): res = data.get("raw_state") == f.state
                elif isinstance(f, MagicFilter): res = f(event)
                elif hasattr(f, "__call__") and inspect.iscoroutinefunction(f.__call__):
                    res = await f(event, **{k: v for k, v in data.items()
                                            if k in inspect.signature(f.__call__).parameters})
                else: res = f(event)
                if res is False or res is None: ok = False; break
                if isinstance(res, dict): extra.update(res)
            if not ok: continue
            d = {**data, **extra}
            async def final(ev, dd, cb=cb):
                return await _call(cb, ev, dd)
            res = await self._wrap(self._inner(), final, event, d)
            return None if res is UNHANDLED else res
        return UNHANDLED


async def _call(cb, event, data):
    sig = inspect.signature(cb)
    params = sig.parameters
    if any(p.kind == p.VAR_KEYWORD for p in params.values()):
        kwargs = dict(data)
    else:
        kwargs = {k: v for k, v in data.items() if k in params}
    names = list(params)
    first = names[0] if names else None
    kwargs.pop(first, None)
    return await cb(event, **kwargs)


class Router:
    def __init__(self, name=None):
        self.name, self.parent, self.sub_routers = name, None, []
        self.message = Observer(self, "message")
        self.callback_query = Observer(self, "callback_query")
        self.errors = self.error = Observer(self, "error")
        self.observers = {"message": self.message, "callback_query": self.callback_query, "error": self.error}
    def include_router(self, r):
        if r.parent is not None: raise RuntimeError("router already attached")
        r.parent = self; self.sub_routers.append(r)
    def include_routers(self, *rs):
        for r in rs: self.include_router(r)
    async def propagate(self, name, event, data):
        obs = self.observers[name]
        async def inner(ev, d):
            res = await obs.trigger(ev, d)
            if res is not UNHANDLED: return res
            for sub in self.sub_routers:
                res = await sub.propagate(name, ev, d)
                if res is not UNHANDLED: return res
            return UNHANDLED
        return await obs._wrap(obs.outer_middleware.items, inner, event, data)
    def used_types(self):
        t = {n for n, o in self.observers.items() if o.handlers and n != "error"}
        for s in self.sub_routers: t |= s.used_types()
        return t


class Dispatcher(Router):
    def __init__(self, *, storage=None, fsm_strategy=None, disable_fsm=False, name=None, **kwargs):
        super().__init__(name)
        if storage and not isinstance(storage, BaseStorage):
            raise TypeError(f"FSM storage should be instance of 'BaseStorage' not {type(storage).__name__}")
        self.fsm_storage = storage or MemoryStorage()
        self.workflow_data = kwargs
    def resolve_used_update_types(self): return sorted(self.used_types())

    async def feed_update(self, bot, update):
        event = update.message or update.callback_query
        name = "message" if update.message else "callback_query"
        msg = update.message or (update.callback_query.message if update.callback_query else None)
        event.bot = bot
        if isinstance(event, CallbackQuery) and event.message is not None: event.message.bot = bot
        user = event.from_user
        key = (bot.id, msg.chat.id, user.id)
        ctx = FSMContext(self.fsm_storage, key)
        data = {**self.workflow_data, "bot": bot, "event_update": update, "event_from_user": user,
                "state": ctx, "raw_state": await ctx.get_state(), "fsm_storage": self.fsm_storage}
        try:
            res = await self.propagate(name, event, data)
        except Exception as exc:  # noqa: BLE001
            r = await self.propagate("error", ErrorEvent(update, exc), data)
            if r is UNHANDLED: raise
            return True
        return res is not UNHANDLED

    async def start_polling(self, *a, **k): raise RuntimeError("sim")


class Bot:  # noqa: E302 — sinovlarda FakeBot ishlatiladi; bu faqat import uchun
    def __init__(self, token, default=None): self.token = token

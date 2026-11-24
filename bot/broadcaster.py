"""Ommaviy xabar yuborish: tezlik cheklovi, xatolarni hisoblash, to'xtatish."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from aiogram import Bot
from aiogram.exceptions import (TelegramAPIError, TelegramBadRequest,
                                TelegramForbiddenError, TelegramRetryAfter)
from aiogram.types import InlineKeyboardMarkup

from bot.services.repo import Repo

logger = logging.getLogger(__name__)

PER_SECOND = 20  # Telegram limiti ~30/s, zaxira bilan
PROGRESS_EVERY = 3.0  # soniya

NotifyFn = Callable[["Job", bool], Awaitable[None]]


@dataclass
class Job:
    id: int
    admin_id: int
    total: int
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    status: str = "running"  # running | done | cancelled | error
    reasons: Counter = field(default_factory=Counter)
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None

    @property
    def processed(self) -> int:
        return self.sent + self.failed + self.blocked

    @property
    def elapsed(self) -> int:
        return int((self.finished or time.monotonic()) - self.started)


class Broadcaster:
    def __init__(self, bot: Bot, repo: Repo, per_second: int = PER_SECOND) -> None:
        self.bot = bot
        self.repo = repo
        self.per_second = per_second
        self.current: Job | None = None
        self._task: asyncio.Task | None = None

    @property
    def busy(self) -> bool:
        return self.current is not None and self.current.status == "running"

    async def start(self, admin_id: int, from_chat_id: int, message_id: int,
                    markup: InlineKeyboardMarkup | None, kind: str, preview: str,
                    notify: NotifyFn) -> Job | None:
        if self.busy:
            return None
        ids = await self.repo.users.broadcast_ids()
        bid = await self.repo.broadcasts.create(admin_id, kind, preview, len(ids))
        job = Job(id=bid, admin_id=admin_id, total=len(ids))
        self.current = job
        self._task = asyncio.create_task(
            self._run(job, ids, from_chat_id, message_id, markup, notify))
        return job

    def stop(self, job_id: int) -> bool:
        if self.current and self.current.id == job_id and self.current.status == "running":
            self.current.cancel.set()
            return True
        return False

    async def _send_one(self, uid: int, job: Job, from_chat_id: int, message_id: int,
                        markup: InlineKeyboardMarkup | None, dead: list[int]) -> None:
        for attempt in range(3):
            try:
                await self.bot.copy_message(chat_id=uid, from_chat_id=from_chat_id,
                                            message_id=message_id, reply_markup=markup)
                job.sent += 1
                return
            except TelegramRetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 1)
            except TelegramForbiddenError:
                job.blocked += 1
                job.reasons["Foydalanuvchi botni bloklagan"] += 1
                dead.append(uid)
                return
            except TelegramBadRequest as exc:
                job.failed += 1
                text = str(exc).lower()
                if "chat not found" in text or "deactivated" in text:
                    job.reasons["Chat topilmadi / akkaunt o'chirilgan"] += 1
                    dead.append(uid)
                else:
                    job.reasons["Telegram rad etdi"] += 1
                return
            except (TelegramAPIError, asyncio.TimeoutError, OSError):
                if attempt == 2:
                    job.failed += 1
                    job.reasons["Tarmoq/Telegram xatosi"] += 1
                    return
                await asyncio.sleep(1 + attempt)
        job.failed += 1
        job.reasons["Limit (qayta urinishlar tugadi)"] += 1

    async def _run(self, job: Job, ids: list[int], from_chat_id: int, message_id: int,
                   markup: InlineKeyboardMarkup | None, notify: NotifyFn) -> None:
        dead: list[int] = []
        last_report = time.monotonic()
        try:
            for i in range(0, len(ids), self.per_second):
                if job.cancel.is_set():
                    job.status = "cancelled"
                    break
                tick = time.monotonic()
                await asyncio.gather(*(
                    self._send_one(uid, job, from_chat_id, message_id, markup, dead)
                    for uid in ids[i:i + self.per_second]))
                if time.monotonic() - last_report >= PROGRESS_EVERY:
                    last_report = time.monotonic()
                    await self.repo.broadcasts.progress(job.id, job.sent, job.failed, job.blocked)
                    await self._safe_notify(notify, job, False)
                rest = 1.0 - (time.monotonic() - tick)
                if rest > 0 and i + self.per_second < len(ids):
                    await asyncio.sleep(rest)
            else:
                job.status = "done"
        except asyncio.CancelledError:
            job.status = "cancelled"
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Xabar yuborishda kutilmagan xato")
            job.status = "error"
        finally:
            job.finished = time.monotonic()
            try:
                await self.repo.broadcasts.finish(job.id, job.status, job.sent, job.failed, job.blocked)
                if dead:
                    await self.repo.users.mark_bot_blocked(dead)
            except Exception:  # noqa: BLE001
                logger.exception("Yuborish natijasini saqlab bo'lmadi")
            await self._safe_notify(notify, job, True)

    @staticmethod
    async def _safe_notify(notify: NotifyFn, job: Job, final: bool) -> None:
        try:
            await notify(job, final)
        except Exception:  # noqa: BLE001
            logger.warning("Jarayon xabarini yangilab bo'lmadi", exc_info=True)

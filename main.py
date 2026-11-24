"""Anime Telegram bot — kirish nuqtasi."""
from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiohttp import web

from bot.handlers import get_routers
from bot.middlewares import UserTrackingMiddleware
from bot.services.access import AccessService
from bot.services.broadcaster import Broadcaster
from bot.services.catalog_client import CatalogClient
from bot.services.database import create_database
from bot.services.repo import Repo
from bot.services.stats import StatsService
from bot.services.storage import create_storage
from bot.utils import timefmt
from config import load_config

logger = logging.getLogger("anime-bot")

COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="search", description="Anime qidirish"),
    BotCommand(command="top", description="Top anime reytingi"),
    BotCommand(command="popular", description="Mashhur animelar"),
    BotCommand(command="genres", description="Anime janrlari"),
    BotCommand(command="recommend", description="Tavsiyalar"),
    BotCommand(command="favorites", description="Sevimli animelar"),
    BotCommand(command="help", description="Yordam"),
]


async def start_health_server(port: int) -> web.AppRunner:
    """Render/Railway web-servis uchun oddiy health-check."""

    async def ok(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", ok)
    app.router.add_get("/health", ok)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info("Health server %s-portda ishga tushdi", port)
    return runner


def build_dispatcher(*, jikan, storage, admin_username: str, repo: Repo, access: AccessService,
                     stats: StatsService, broadcaster: Broadcaster, started_at: float) -> Dispatcher:
    """Dispatcher, middleware va routerlarni yig'adi (sinovlarda ham shu funksiya ishlatiladi)."""
    # DIQQAT: Dispatcher(storage=...) aiogram'ning FSM saqlagichi uchun band (admin panel FSM ishlatadi),
    # shuning uchun sevimlilar saqlagichi workflow_data orqali beriladi — handlerlar o'zgarmaydi.
    dp = Dispatcher(
        jikan=jikan, admin_username=admin_username, repo=repo, access=access,
        stats=stats, broadcaster=broadcaster, started_at=started_at,
    )
    dp.workflow_data["storage"] = storage
    tracking = UserTrackingMiddleware(repo, access)
    dp.message.outer_middleware(tracking)
    dp.callback_query.outer_middleware(tracking)
    dp.include_routers(*get_routers())
    return dp


async def main() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    started_at = time.time()
    timefmt.configure(cfg.tz_offset_hours)

    storage = create_storage(cfg.database_url)
    await storage.init()

    # Admin paneli ma'lumotlari: shu DATABASE_URL (PostgreSQL) yoki lokal SQLite
    repo = Repo(create_database(cfg.database_url, cfg.sqlite_path))
    await repo.start()
    access = AccessService(
        repo, cfg.super_admin_username, cfg.super_admin_ids, cfg.admin_ids,
        cfg.setup_code, cfg.reset_super_binding,
    )
    await access.load()

    jikan = CatalogClient(cfg.jikan_base_url, cfg.cache_ttl, repo.catalog)
    await jikan.start()

    bot = Bot(
        cfg.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML, link_preview_is_disabled=True
        ),
    )
    stats = StatsService(repo, storage, access, jikan,
                         "PostgreSQL" if cfg.database_url else f"SQLite ({cfg.sqlite_path})")
    broadcaster = Broadcaster(bot, repo)
    dp = build_dispatcher(
        jikan=jikan, storage=storage, admin_username=cfg.admin_username, repo=repo,
        access=access, stats=stats, broadcaster=broadcaster, started_at=started_at,
    )

    runner = await start_health_server(cfg.port) if cfg.port else None
    try:
        await bot.set_my_commands(COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        me = await bot.get_me()
        logger.info("Bot ishga tushdi: @%s", me.username)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if broadcaster.busy:
            broadcaster.current.cancel.set()
        await bot.session.close()
        await jikan.close()
        await storage.close()
        await repo.close()
        if runner:
            await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")

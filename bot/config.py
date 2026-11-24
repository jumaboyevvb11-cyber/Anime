"""Muhit o'zgaruvchilaridan sozlamalarni o'qish."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str | None
    jikan_base_url: str
    cache_ttl: int
    log_level: str
    port: int | None
    admin_username: str
    # ---- Admin panel ----
    super_admin_username: str = "jumaboyev101"
    super_admin_ids: frozenset[int] = field(default_factory=frozenset)
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    setup_code: str | None = None
    reset_super_binding: bool = False
    sqlite_path: str = "data/bot.db"
    tz_offset_hours: int = 5  # Asia/Tashkent (UTC+5)


def _parse_ids(raw: str, name: str) -> frozenset[int]:
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if part.lstrip("-").isdigit():
            ids.add(int(part))
        else:
            logger.warning("%s ichida noto'g'ri qiymat o'tkazib yuborildi: %r", name, part)
    return frozenset(ids)


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylga yoki hosting o'zgaruvchilariga qo'shing."
        )
    port = os.getenv("PORT", "").strip()
    admin_username = os.getenv("ADMIN_USERNAME", "jumaboyev101").strip().lstrip("@")
    setup_code = os.getenv("SUPER_ADMIN_SETUP_CODE", "").strip() or None
    if setup_code and len(setup_code) < 8:
        raise RuntimeError("SUPER_ADMIN_SETUP_CODE kamida 8 ta belgidan iborat bo'lishi kerak.")
    tz = os.getenv("TIMEZONE_OFFSET", "5").strip()
    return Config(
        bot_token=token,
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
        jikan_base_url="https://api.jikan.moe/v4",
        cache_ttl=int(os.getenv("CACHE_TTL", "600")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        port=int(port) if port.isdigit() else None,
        admin_username=admin_username,
        super_admin_username=(
            os.getenv("SUPER_ADMIN_USERNAME", "").strip().lstrip("@") or admin_username
        ),
        super_admin_ids=_parse_ids(os.getenv("SUPER_ADMIN_IDS", ""), "SUPER_ADMIN_IDS"),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", ""), "ADMIN_IDS"),
        setup_code=setup_code,
        reset_super_binding=_flag("RESET_SUPER_ADMIN_BINDING"),
        sqlite_path=os.getenv("SQLITE_PATH", "data/bot.db").strip() or "data/bot.db",
        tz_offset_hours=int(tz) if tz.lstrip("-").isdigit() else 5,
    )

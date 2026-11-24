"""Admin paneli uchun ma'lumotlar bazasi adapteri.

* ``DATABASE_URL`` bor bo'lsa — PostgreSQL (asyncpg), sevimlilar bilan BIR XIL baza.
* Yo'q bo'lsa — lokal SQLite fayl (``SQLITE_PATH``, standart ``data/bot.db``).

Barcha so'rovlar bitta portativ SQL dialektida (``$1, $2`` parametrlar) yoziladi,
SQLite uchun avtomatik ``?1, ?2`` ga o'giriladi. Vaqtlar UNIX soniyalarda (BIGINT),
mantiqiy qiymatlar 0/1 (INTEGER) sifatida saqlanadi — ikkala bazada bir xil ishlaydi.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import threading
from typing import Any

logger = logging.getLogger(__name__)

_PARAM = re.compile(r"\$(\d+)")


class Database:
    dialect = "base"

    async def start(self) -> None: ...
    async def close(self) -> None: ...

    async def execute(self, sql: str, *args: Any) -> int:
        """So'rovni bajaradi, ta'sirlangan qatorlar sonini qaytaradi."""
        raise NotImplementedError

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any] | None:
        rows = await self.fetch(sql, *args)
        return rows[0] if rows else None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        row = await self.fetchrow(sql, *args)
        return next(iter(row.values())) if row else None

    async def init_schema(self) -> None:
        serial = "BIGSERIAL PRIMARY KEY" if self.dialect == "postgres" else (
            "INTEGER PRIMARY KEY AUTOINCREMENT"
        )
        for stmt in SCHEMA:
            await self.execute(stmt.replace("{SERIAL}", serial))


class PostgresDatabase(Database):
    dialect = "postgres"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool = None

    async def start(self) -> None:
        import asyncpg

        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        await self.init_schema()
        logger.info("Admin bazasi: PostgreSQL")

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def execute(self, sql: str, *args: Any) -> int:
        status = await self.pool.execute(sql, *args)
        try:
            return int(str(status).split()[-1])
        except (ValueError, IndexError):
            return 0

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return [dict(r) for r in await self.pool.fetch(sql, *args)]


class SQLiteDatabase(Database):
    dialect = "sqlite"

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    async def start(self) -> None:
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self._conn = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        await self.init_schema()
        logger.warning(
            "Admin bazasi: SQLite (%s). Hostingda doimiy saqlash uchun DATABASE_URL (PostgreSQL) ulang.",
            self.path,
        )

    async def close(self) -> None:
        if self._conn:
            with self._lock:
                self._conn.close()
            self._conn = None

    def _run(self, sql: str, args: tuple, want_rows: bool):
        sql = _PARAM.sub(r"?\1", sql)
        with self._lock:
            cur = self._conn.execute(sql, args)
            if want_rows:
                return [dict(r) for r in cur.fetchall()]
            if cur.description is not None:  # RETURNING bor so'rov
                cur.fetchall()
            return cur.rowcount

    async def execute(self, sql: str, *args: Any) -> int:
        return await asyncio.to_thread(self._run, sql, args, False)

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._run, sql, args, True)


def create_database(database_url: str | None, sqlite_path: str) -> Database:
    return PostgresDatabase(database_url) if database_url else SQLiteDatabase(sqlite_path)


SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        user_id     BIGINT PRIMARY KEY,
        name        TEXT NOT NULL DEFAULT '',
        username    TEXT,
        joined_at   BIGINT NOT NULL,
        last_active BIGINT NOT NULL,
        is_blocked  INTEGER NOT NULL DEFAULT 0,
        blocked_at  BIGINT,
        blocked_by  BIGINT,
        bot_blocked INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)",
    "CREATE INDEX IF NOT EXISTS idx_users_joined ON users(joined_at)",
    """CREATE TABLE IF NOT EXISTS search_logs (
        id      {SERIAL},
        user_id BIGINT NOT NULL,
        term    TEXT NOT NULL,
        results INTEGER NOT NULL DEFAULT 0,
        ts      BIGINT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_search_ts ON search_logs(ts)",
    "CREATE INDEX IF NOT EXISTS idx_search_user ON search_logs(user_id, ts)",
    """CREATE TABLE IF NOT EXISTS anime_stats (
        anime_id BIGINT PRIMARY KEY,
        title    TEXT NOT NULL,
        views    BIGINT NOT NULL DEFAULT 0,
        last_ts  BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS counters (
        name TEXT PRIMARY KEY,
        val  BIGINT NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS custom_anime (
        id         {SERIAL},
        title      TEXT NOT NULL,
        title_en   TEXT,
        synopsis   TEXT,
        genres     TEXT,
        anime_type TEXT,
        episodes   INTEGER,
        year       INTEGER,
        status     TEXT,
        score      REAL,
        photo      TEXT,
        created_by BIGINT,
        created_at BIGINT NOT NULL,
        updated_at BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS featured (
        kind     TEXT NOT NULL,
        anime_id BIGINT NOT NULL,
        title    TEXT NOT NULL,
        score    REAL,
        pos      INTEGER NOT NULL,
        added_by BIGINT,
        added_at BIGINT NOT NULL,
        PRIMARY KEY (kind, anime_id)
    )""",
    """CREATE TABLE IF NOT EXISTS admins (
        user_id  BIGINT PRIMARY KEY,
        role     TEXT NOT NULL,
        perms    TEXT NOT NULL DEFAULT '',
        name     TEXT NOT NULL DEFAULT '',
        username TEXT,
        added_by BIGINT,
        added_at BIGINT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS admin_logs (
        id         {SERIAL},
        admin_id   BIGINT NOT NULL,
        admin_name TEXT NOT NULL DEFAULT '',
        action     TEXT NOT NULL,
        details    TEXT NOT NULL DEFAULT '',
        ts         BIGINT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_admin_logs_ts ON admin_logs(ts)",
    """CREATE TABLE IF NOT EXISTS broadcasts (
        id          {SERIAL},
        admin_id    BIGINT NOT NULL,
        kind        TEXT NOT NULL,
        preview     TEXT NOT NULL DEFAULT '',
        total       INTEGER NOT NULL DEFAULT 0,
        sent        INTEGER NOT NULL DEFAULT 0,
        failed      INTEGER NOT NULL DEFAULT 0,
        blocked     INTEGER NOT NULL DEFAULT 0,
        status      TEXT NOT NULL DEFAULT 'running',
        started_at  BIGINT NOT NULL,
        finished_at BIGINT
    )""",
]

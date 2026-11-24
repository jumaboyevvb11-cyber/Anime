"""Adminlar va harakatlar tarixi."""
from __future__ import annotations

from typing import Any

from bot.services.database import Database
from bot.utils import timefmt

Row = dict[str, Any]


class AdminsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def all(self) -> list[Row]:
        return await self.db.fetch("SELECT * FROM admins ORDER BY role DESC, added_at")

    async def get(self, user_id: int) -> Row | None:
        return await self.db.fetchrow("SELECT * FROM admins WHERE user_id=$1", user_id)

    async def add(self, user_id: int, role: str, perms: str, name: str,
                  username: str | None, added_by: int | None) -> None:
        await self.db.execute(
            "INSERT INTO admins (user_id, role, perms, name, username, added_by, added_at) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) "
            "ON CONFLICT (user_id) DO UPDATE SET role=excluded.role, perms=excluded.perms, "
            "name=excluded.name, username=excluded.username",
            user_id, role, perms, name[:100], username, added_by, timefmt.now(),
        )

    async def add_if_missing(self, user_id: int, perms: str) -> bool:
        n = await self.db.execute(
            "INSERT INTO admins (user_id, role, perms, name, added_at) "
            "VALUES ($1,'admin',$2,'',$3) ON CONFLICT (user_id) DO NOTHING",
            user_id, perms, timefmt.now(),
        )
        return bool(n)

    async def update_profile(self, user_id: int, name: str, username: str | None) -> None:
        await self.db.execute(
            "UPDATE admins SET name=$2, username=$3 WHERE user_id=$1", user_id, name[:100], username)

    async def set_perms(self, user_id: int, perms: str) -> bool:
        return bool(await self.db.execute(
            "UPDATE admins SET perms=$2 WHERE user_id=$1 AND role='admin'", user_id, perms))

    async def remove(self, user_id: int) -> bool:
        return bool(await self.db.execute(
            "DELETE FROM admins WHERE user_id=$1 AND role='admin'", user_id))

    async def delete_super(self) -> int:
        return await self.db.execute("DELETE FROM admins WHERE role='super'")


class LogsRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add(self, admin_id: int, admin_name: str, action: str, details: str = "") -> None:
        await self.db.execute(
            "INSERT INTO admin_logs (admin_id, admin_name, action, details, ts) "
            "VALUES ($1,$2,$3,$4,$5)",
            admin_id, admin_name[:100], action, details[:500], timefmt.now(),
        )

    async def count(self, admin_id: int | None = None) -> int:
        if admin_id is None:
            return await self.db.fetchval("SELECT count(*) FROM admin_logs") or 0
        return await self.db.fetchval(
            "SELECT count(*) FROM admin_logs WHERE admin_id=$1", admin_id) or 0

    async def page(self, limit: int, offset: int, admin_id: int | None = None) -> list[Row]:
        if admin_id is None:
            return await self.db.fetch(
                "SELECT * FROM admin_logs ORDER BY ts DESC, id DESC LIMIT $1 OFFSET $2",
                limit, offset)
        return await self.db.fetch(
            "SELECT * FROM admin_logs WHERE admin_id=$1 ORDER BY ts DESC, id DESC "
            "LIMIT $2 OFFSET $3", admin_id, limit, offset)

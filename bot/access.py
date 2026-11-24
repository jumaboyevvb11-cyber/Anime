"""Admin huquqlari va Super Admin ni xavfsiz bog'lash (claim) mexanizmi.

Qoidalar:
* Admin faqat Telegram ID orqali aniqlanadi (username ishonchli emas — o'zgarishi mumkin).
* Super Admin ID si ikki yo'ldan biri bilan belgilanadi:
    1. ``SUPER_ADMIN_IDS`` muhit o'zgaruvchisi (hoster aniq biladi), yoki
    2. ``/claim <kod>``: kod faqat server logida (yoki ``SUPER_ADMIN_SETUP_CODE`` da) bor,
       va yuboruvchining Telegram username i ``SUPER_ADMIN_USERNAME`` ga mos bo'lishi shart.
       Muvaffaqiyatli bo'lsa ID bazaga yoziladi va keyingi barcha tekshiruvlar ID bo'yicha.
* Super Admin huquqlarini hech kim (boshqa adminlar ham) o'zgartira olmaydi.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from enum import Enum

from bot.services.repo import Repo

logger = logging.getLogger(__name__)

PERMS: dict[str, str] = {
    "stats": "📊 Statistika",
    "users": "👥 Foydalanuvchilar",
    "broadcast": "📣 Xabar yuborish",
    "anime": "🎬 Anime boshqaruvi",
    "admins": "⚙️ Adminlar va tarix",
}
ALL_PERMS = frozenset(PERMS)
DEFAULT_NEW_ADMIN_PERMS = frozenset({"stats"})
ENV_ADMIN_PERMS = frozenset({"stats", "users", "broadcast", "anime"})

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
MAX_FAILS_PER_USER = 5
USER_WINDOW = 15 * 60
MAX_FAILS_GLOBAL = 30
GLOBAL_WINDOW = 3600


@dataclass(frozen=True)
class AdminInfo:
    user_id: int
    role: str  # "super" | "admin"
    perms: frozenset[str]
    name: str = ""
    username: str | None = None

    @property
    def is_super(self) -> bool:
        return self.role == "super"

    def can(self, perm: str) -> bool:
        return self.is_super or perm in self.perms


class ClaimResult(Enum):
    OK = "ok"
    DISABLED = "disabled"  # Super Admin allaqachon bog'langan
    LOCKED = "locked"      # juda ko'p noto'g'ri urinish
    WRONG = "wrong"


def _norm_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def generate_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def parse_perms(raw: str) -> frozenset[str]:
    return frozenset(p for p in raw.split(",") if p in ALL_PERMS)


def dump_perms(perms: frozenset[str] | set[str]) -> str:
    return ",".join(p for p in PERMS if p in perms)  # barqaror tartib


class AccessService:
    def __init__(self, repo: Repo, super_username: str, env_super_ids: frozenset[int],
                 env_admin_ids: frozenset[int] = frozenset(), setup_code: str | None = None,
                 reset_binding: bool = False) -> None:
        self.repo = repo
        self.super_username = super_username.lstrip("@").casefold()
        self.env_super_ids = frozenset(env_super_ids)
        self.env_admin_ids = frozenset(env_admin_ids)
        self._static_code = setup_code
        self._reset = reset_binding
        self._code: str | None = None
        self._cache: dict[int, AdminInfo] = {}
        self._lock = asyncio.Lock()
        self._profiles: dict[int, tuple[str, str | None]] = {}  # env-superlar uchun ism/username
        self._fails: dict[int, list[float]] = {}
        self._global_fails: list[float] = []

    # ---------- yuklash ----------
    async def load(self) -> None:
        if self._reset:
            n = await self.repo.admins.delete_super()
            logger.warning("RESET_SUPER_ADMIN_BINDING: %s ta Super Admin bog'lanishi o'chirildi. "
                           "Ishga tushgach bu o'zgaruvchini olib tashlang!", n)
        for uid in self.env_admin_ids - self.env_super_ids:
            await self.repo.admins.add_if_missing(uid, ",".join(p for p in PERMS if p in ENV_ADMIN_PERMS))
        await self.refresh()
        if self.claim_enabled:
            self._code = self._static_code or generate_code()
            if self._static_code:
                logger.warning("SUPER ADMIN hali bog'lanmagan. @%s botga /claim <SUPER_ADMIN_SETUP_CODE> "
                               "yuborsin.", self.super_username)
            else:
                logger.warning("SUPER ADMIN hali bog'lanmagan. @%s akkauntidan botga yuboring:  /claim %s",
                               self.super_username, self._code)
        else:
            self._code = None

    async def refresh(self) -> None:
        cache: dict[int, AdminInfo] = {}
        for r in await self.repo.admins.all():
            cache[r["user_id"]] = AdminInfo(
                r["user_id"], r["role"], parse_perms(r["perms"]), r["name"], r["username"])
        for uid in self.env_super_ids:
            old = cache.get(uid)
            name, uname = self._profiles.get(uid) or ((old.name, old.username) if old else ("", None))
            cache[uid] = AdminInfo(uid, "super", ALL_PERMS, name, uname)
        self._cache = cache

    async def sync_profile(self, user_id: int, name: str, username: str | None) -> None:
        """Admin ismi/username i o'zgarganda (yoki bo'sh bo'lsa) yangilaydi."""
        a = self._cache.get(user_id)
        if a is None or (a.name == name and a.username == username):
            return
        self._profiles[user_id] = (name, username)
        await self.repo.admins.update_profile(user_id, name, username)
        await self.refresh()

    # ---------- tekshiruvlar ----------
    def get(self, user_id: int) -> AdminInfo | None:
        return self._cache.get(user_id)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._cache

    def is_super(self, user_id: int) -> bool:
        a = self._cache.get(user_id)
        return bool(a and a.is_super)

    def supers(self) -> list[AdminInfo]:
        return [a for a in self._cache.values() if a.is_super]

    def admins(self) -> list[AdminInfo]:
        return sorted(self._cache.values(), key=lambda a: (not a.is_super, a.user_id))

    @property
    def claim_enabled(self) -> bool:
        return not any(a.is_super for a in self._cache.values())

    # ---------- adminlarni boshqarish ----------
    async def add_admin(self, user_id: int, name: str, username: str | None, by: int,
                        perms: frozenset[str] = DEFAULT_NEW_ADMIN_PERMS) -> bool:
        if user_id in self._cache:
            return False
        await self.repo.admins.add(user_id, "admin", dump_perms(perms), name, username, by)
        await self.refresh()
        return True

    async def set_perms(self, user_id: int, perms: frozenset[str]) -> bool:
        a = self._cache.get(user_id)
        if not a or a.is_super:
            return False
        ok = await self.repo.admins.set_perms(user_id, dump_perms(perms))
        await self.refresh()
        return ok

    async def remove_admin(self, user_id: int) -> bool:
        a = self._cache.get(user_id)
        if not a or a.is_super:
            return False
        ok = await self.repo.admins.remove(user_id)
        await self.refresh()
        return ok

    # ---------- Super Admin ni bog'lash ----------
    def _prune(self, stamps: list[float], window: int) -> list[float]:
        cutoff = time.monotonic() - window
        return [t for t in stamps if t > cutoff]

    async def try_claim(self, user_id: int, username: str | None, name: str,
                        code: str) -> ClaimResult:
        async with self._lock:
            if not self.claim_enabled or not self._code:
                return ClaimResult.DISABLED
            mine = self._fails[user_id] = self._prune(self._fails.get(user_id, []), USER_WINDOW)
            self._global_fails = self._prune(self._global_fails, GLOBAL_WINDOW)
            if len(mine) >= MAX_FAILS_PER_USER or len(self._global_fails) >= MAX_FAILS_GLOBAL:
                return ClaimResult.LOCKED
            code_ok = secrets.compare_digest(_norm_code(code), _norm_code(self._code))
            name_ok = bool(username) and username.casefold() == self.super_username
            if not (code_ok and name_ok):
                now = time.monotonic()
                mine.append(now)
                self._global_fails.append(now)
                logger.warning("Super Admin claim rad etildi: id=%s username=%s", user_id, username)
                return ClaimResult.WRONG
            await self.repo.admins.add(user_id, "super", dump_perms(ALL_PERMS), name, username, user_id)
            await self.repo.logs.add(user_id, name, "super_claim",
                                     f"Super Admin ID bog'landi: {user_id} (@{username})")
            await self.refresh()
            self._code = None
            self._fails.pop(user_id, None)
            logger.warning("SUPER ADMIN bog'landi: id=%s username=%s", user_id, username)
            return ClaimResult.OK

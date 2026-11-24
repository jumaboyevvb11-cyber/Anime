"""Vaqt yordamchilari. Barcha vaqtlar bazada UNIX soniyalarda (UTC) saqlanadi."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

_offset_hours = 5  # Asia/Tashkent


def configure(offset_hours: int) -> None:
    global _offset_hours
    _offset_hours = offset_hours


def tz_offset_seconds() -> int:
    return _offset_hours * 3600


def now() -> int:
    return int(time.time())


def _local(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, timezone(timedelta(hours=_offset_hours)))


def day_start(ts: int | None = None) -> int:
    """Mahalliy vaqt bo'yicha kun boshi (UNIX soniya)."""
    ts = now() if ts is None else ts
    off = tz_offset_seconds()
    return ((ts + off) // 86400) * 86400 - off


def fmt_dt(ts: int | None) -> str:
    return _local(ts).strftime("%d.%m.%Y %H:%M") if ts else "—"


def fmt_short(ts: int | None) -> str:
    return _local(ts).strftime("%d.%m %H:%M") if ts else "—"


def fmt_day(ts: int) -> str:
    return _local(ts).strftime("%d.%m")


def fmt_duration(seconds: int) -> str:
    seconds = max(int(seconds), 0)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d} kun")
    if h:
        parts.append(f"{h} soat")
    if m and not d:
        parts.append(f"{m} daq")
    if not parts:
        parts.append(f"{s} soniya")
    return " ".join(parts)


def ago(ts: int | None) -> str:
    if not ts:
        return "—"
    diff = now() - ts
    if diff < 60:
        return "hozir"
    if diff < 3600:
        return f"{diff // 60} daqiqa oldin"
    if diff < 86400:
        return f"{diff // 3600} soat oldin"
    return f"{diff // 86400} kun oldin"

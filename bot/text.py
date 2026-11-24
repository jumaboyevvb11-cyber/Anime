"""Matn formatlash: anime kartochkasi va o'zbekcha tarjimalar."""
from __future__ import annotations

import html
import re
from typing import Any

CAPTION_LIMIT = 1024

esc = html.escape

STATUS_UZ = {
    "Finished Airing": "Tugagan ✅",
    "Currently Airing": "Efirda 📡",
    "Not yet aired": "Hali chiqmagan 🕐",
}
TYPE_UZ = {
    "TV": "TV serial", "Movie": "Film", "OVA": "OVA", "ONA": "ONA",
    "Special": "Maxsus", "Music": "Musiqa", "TV Special": "TV maxsus",
}
GENRE_UZ = {
    "Action": "Jangari", "Adventure": "Sarguzasht", "Avant Garde": "Avangard",
    "Award Winning": "Mukofotli", "Boys Love": "Boys Love", "Comedy": "Komediya",
    "Drama": "Drama", "Fantasy": "Fantaziya", "Girls Love": "Girls Love",
    "Gourmet": "Gastronomiya", "Horror": "Qo'rqinchli", "Mystery": "Sirli",
    "Romance": "Romantika", "Sci-Fi": "Ilmiy fantastika",
    "Slice of Life": "Kundalik hayot", "Sports": "Sport",
    "Supernatural": "G'ayritabiiy", "Suspense": "Triller", "Ecchi": "Ecchi",
}


def genre_uz(name: str) -> str:
    return GENRE_UZ.get(name, name)


def get_image(anime: dict[str, Any]) -> str | None:
    jpg = (anime.get("images") or {}).get("jpg") or {}
    return jpg.get("large_image_url") or jpg.get("image_url")


def _duration(raw: str | None) -> str | None:
    if not raw or raw == "Unknown":
        return None
    return (raw.replace(" per ep", " / qism").replace(" hr", " soat")
            .replace(" min", " daq").replace(" sec", " soniya"))


def _synopsis(raw: str | None) -> str:
    if not raw:
        return ""
    raw = re.sub(r"\[Written by .*?\]", "", raw)
    raw = re.sub(r"\(Source:.*?\)", "", raw)
    return re.sub(r"\s+", " ", raw).strip()


def build_caption(a: dict[str, Any]) -> str:
    title = a.get("title") or "Noma'lum"
    lines = [f"🎌 <b>{esc(title)}</b>"]
    if (eng := a.get("title_english")) and eng != title:
        lines.append(f"🇬🇧 {esc(eng)}")
    if jp := a.get("title_japanese"):
        lines.append(f"🇯🇵 {esc(jp)}")
    lines.append("")

    if score := a.get("score"):
        votes = f" ({a['scored_by']:,} ovoz)".replace(",", " ") if a.get("scored_by") else ""
        lines.append(f"⭐ <b>Reyting:</b> {score}{votes}")
    if a.get("rank"):
        lines.append(f"🏆 <b>Top o'rin:</b> #{a['rank']}")
    if a.get("popularity"):
        lines.append(f"🔥 <b>Mashhurlik:</b> #{a['popularity']}")

    kind = TYPE_UZ.get(a.get("type") or "", a.get("type") or "—")
    eps = f" · {a['episodes']} qism" if a.get("episodes") else ""
    lines.append(f"📺 <b>Turi:</b> {esc(kind)}{eps}")
    if status := a.get("status"):
        lines.append(f"📌 <b>Holati:</b> {STATUS_UZ.get(status, esc(status))}")
    if aired := (a.get("aired") or {}).get("string"):
        lines.append(f"📅 <b>Efir:</b> {esc(aired)}")
    if dur := _duration(a.get("duration")):
        lines.append(f"⏱ <b>Davomiyligi:</b> {esc(dur)}")
    if studios := [s["name"] for s in a.get("studios") or []][:2]:
        lines.append(f"🏢 <b>Studiya:</b> {esc(', '.join(studios))}")
    if genres := [genre_uz(g["name"]) for g in a.get("genres") or []]:
        lines.append(f"🎭 <b>Janrlar:</b> {esc(', '.join(genres))}")

    header = "\n".join(lines)
    syn = _synopsis(a.get("synopsis"))
    if not syn:
        return header

    lang = "" if a.get("_custom") else " <i>(inglizcha)</i>"  # admin qo'shgan animeda til belgisi yo'q
    prefix = f"\n\n📖 <b>Qisqacha mazmun</b>{lang}\n"
    budget = CAPTION_LIMIT - len(header) - len(prefix) - 2
    if budget < 80:
        return header
    text = syn
    cut = False
    while len(esc(text)) > budget:
        text = text[: int(len(text) * 0.9)].rsplit(" ", 1)[0]
        cut = True
    return f"{header}{prefix}{esc(text.rstrip())}{'…' if cut else ''}"


def button_label(a: dict[str, Any], number: int | None = None) -> str:
    title = a.get("title_english") or a.get("title") or "Noma'lum"
    score = a.get("score")
    prefix = f"{number}. " if number else ""
    star = f"⭐{score:.1f} · " if isinstance(score, (int, float)) and score else ""
    label = f"{prefix}{star}{title}"
    return label if len(label) <= 60 else label[:57] + "…"

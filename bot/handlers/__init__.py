from aiogram import Router

from . import anime, browse, errors, favorites, featured, search, start
from .admin import get_admin_routers


def get_routers() -> list[Router]:
    # Tartib muhim: admin routerlari birinchi (FSM kiritishlari qidiruvga tushib ketmasligi uchun),
    # oddiy matn (qidiruv) handleri eng oxirida.
    return [*get_admin_routers(), start.router, browse.router, anime.router, favorites.router,
            featured.router, errors.router, search.router]

"""Admin panel routerlari."""
from aiogram import Router

from . import admins, anime, broadcast, featured, logs, panel, setup, stats, users


def get_admin_routers() -> list[Router]:
    return [setup.router, panel.router, stats.router, users.router, broadcast.router,
            anime.router, featured.router, admins.router, logs.router]

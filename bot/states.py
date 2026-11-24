"""Admin panel FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class UserSearchSG(StatesGroup):
    waiting = State()


class BroadcastSG(StatesGroup):
    content = State()
    button = State()


class AnimeFormSG(StatesGroup):
    input = State()


class FeaturedSG(StatesGroup):
    query = State()


class AdminSG(StatesGroup):
    target = State()

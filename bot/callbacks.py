from aiogram.filters.callback_data import CallbackData


class AnimeCB(CallbackData, prefix="an"):
    id: int


class PageCB(CallbackData, prefix="pg"):
    kind: str  # top | pop | genre | fav
    page: int = 1
    arg: int = 0


class FavCB(CallbackData, prefix="fv"):
    id: int
    act: str  # add | del


class SimCB(CallbackData, prefix="sm"):
    id: int


CB_GENRES = "genres"
CB_RANDOM = "random"
CB_REC_FAV = "rec_fav"
CB_NOOP = "noop"
CB_FEATURED = "featured"

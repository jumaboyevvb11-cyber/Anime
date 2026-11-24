"""Admin panel callback ma'lumotlari. Prefiks: ``ad`` (mavjud prefikslar bilan to'qnashmaydi).

Format: ad:<bo'lim>:<amal>:<id>:<sahifa>:<arg>   (jami <= 64 bayt)
"""
from aiogram.filters.callback_data import CallbackData


class AdmCB(CallbackData, prefix="ad"):
    sec: str            # home | stats | users | bc | an | fa | adm | log
    act: str = "menu"
    id: int = 0
    page: int = 0
    arg: str = ""

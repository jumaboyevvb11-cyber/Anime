"""Global xatolarni qayta ishlash."""
import logging

from aiogram import Bot, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import ErrorEvent

from bot.services.jikan import JikanError

router = Router(name="errors")
logger = logging.getLogger(__name__)

GENERIC = "⚠️ Kutilmagan xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring."


@router.error()
async def on_error(event: ErrorEvent, bot: Bot) -> bool:
    exc = event.exception
    if isinstance(exc, TelegramForbiddenError):  # foydalanuvchi botni bloklagan
        return True

    update = event.update
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query:
        chat_id = update.callback_query.from_user.id
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    if isinstance(exc, JikanError):
        text = exc.user_message
    else:
        logger.exception("Kutilmagan xato", exc_info=exc)
        text = GENERIC

    if chat_id:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.warning("Xato xabarini yuborib bo'lmadi")
    return True

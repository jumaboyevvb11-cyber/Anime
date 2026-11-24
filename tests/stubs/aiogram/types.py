"""aiogram.types ning sinov uchun soddalashtirilgan nusxasi (Telegram cheklovlari tekshiriladi)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

TelegramObject = object


@dataclass
class User:
    id: int
    first_name: str = "U"
    last_name: str | None = None
    username: str | None = None
    is_bot: bool = False
    @property
    def full_name(self): return self.first_name + (f" {self.last_name}" if self.last_name else "")


@dataclass
class Chat:
    id: int
    type: str = "private"


class InlineKeyboardButton:
    def __init__(self, *, text, callback_data=None, url=None):
        if not text: raise ValueError("button text is empty")
        if callback_data is None and url is None: raise ValueError("button needs callback_data or url")
        if callback_data is not None and len(callback_data.encode()) > 64:
            raise ValueError(f"callback_data > 64 bytes: {callback_data!r}")
        self.text, self.callback_data, self.url = text, callback_data, url
    def __repr__(self): return f"Btn({self.text!r})"


class InlineKeyboardMarkup:
    def __init__(self, *, inline_keyboard):
        if len(inline_keyboard) > 100: raise ValueError("too many rows")
        for row in inline_keyboard:
            if not row: raise ValueError("empty row")
            if len(row) > 8: raise ValueError("too many buttons in a row")
        self.inline_keyboard = inline_keyboard
    def __eq__(self, o): return isinstance(o, InlineKeyboardMarkup) and self.flat() == o.flat()
    def flat(self): return [[(b.text, b.callback_data, b.url) for b in r] for r in self.inline_keyboard]


class KeyboardButton:
    def __init__(self, *, text): self.text = text

class ReplyKeyboardMarkup:
    def __init__(self, *, keyboard, resize_keyboard=None, input_field_placeholder=None):
        self.keyboard = keyboard

class BotCommand:
    def __init__(self, *, command, description): self.command, self.description = command, description

class PhotoSize:
    def __init__(self, file_id): self.file_id = file_id


class Message:
    def __init__(self, *, message_id, chat, from_user=None, text=None, caption=None, photo=None, bot=None):
        self.message_id, self.chat, self.from_user = message_id, chat, from_user
        self.text, self.caption, self.photo, self.bot = text, caption, photo, bot
    async def answer(self, text, reply_markup=None, **kw):
        return await self.bot.send_message(self.chat.id, text, reply_markup=reply_markup)
    async def answer_photo(self, photo, caption=None, reply_markup=None, **kw):
        return await self.bot.send_photo(self.chat.id, photo, caption=caption, reply_markup=reply_markup)
    async def edit_text(self, text, reply_markup=None, **kw):
        return await self.bot.edit_message_text(text, chat_id=self.chat.id, message_id=self.message_id,
                                                reply_markup=reply_markup)
    async def edit_reply_markup(self, reply_markup=None, **kw):
        return await self.bot.edit_message_reply_markup(chat_id=self.chat.id, message_id=self.message_id,
                                                        reply_markup=reply_markup)
    async def delete(self):
        return await self.bot.delete_message(self.chat.id, self.message_id)


class CallbackQuery:
    def __init__(self, *, id, from_user, message, data, bot=None):
        self.id, self.from_user, self.message, self.data, self.bot = id, from_user, message, data, bot
    async def answer(self, text=None, show_alert=False, **kw):
        return await self.bot.answer_callback_query(self.id, text=text, show_alert=show_alert)


@dataclass
class Update:
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None


@dataclass
class ErrorEvent:
    update: Update
    exception: Exception

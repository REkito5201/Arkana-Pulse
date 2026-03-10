"""
Антиспам: вместо нового сообщения на каждую команду редактируем последнее сообщение бота в чате.
Последний message_id храним в Redis (ключ по chat_id). Если редактирование невозможно — шлём новое и обновляем ключ.
"""
from __future__ import annotations

import logging
from typing import Any

from aiogram import types
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

# Ключ Redis: message_id последнего сообщения бота в этом чате. Редактируем его при следующем ответе.
LAST_BOT_MSG_KEY = "bot:last_msg_id:{chat_id}"
# TTL 7 дней: если пользователь неделю не писал, ключ удалится — следующий ответ будет новым сообщением.
LAST_BOT_MSG_TTL = 7 * 24 * 3600


async def reply_or_edit(
    message: types.Message,
    text: str,
    parse_mode: str | None = "Markdown",
    reply_markup: types.InlineKeyboardMarkup | None = None,
    **kwargs: Any,
) -> None:
    """
    Отвечает в чат без спама: пытается отредактировать последнее сообщение бота;
    если не вышло (сообщение старое, удалено или контент не изменился) — отправляет новое и запоминает его id.
    Все аргументы после text передаются в answer() или edit_message_text() (parse_mode, reply_markup и т.д.).
    """
    chat_id = message.chat.id
    key = LAST_BOT_MSG_KEY.format(chat_id=chat_id)
    last_id = await redis_client.get(key)

    if last_id:
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=int(last_id),
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs,
            )
            return
        except TelegramBadRequest as e:
            # Сообщение не найдено, устарело для редактирования или текст тот же — шлём новое.
            logger.debug("Edit failed for chat_id=%s: %s", chat_id, e)
        except (ValueError, TypeError):
            logger.warning("Invalid last_msg_id in Redis for chat_id=%s", chat_id)

    msg = await message.answer(
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
        **kwargs,
    )
    await redis_client.set(key, str(msg.message_id))
    await redis_client.expire(key, LAST_BOT_MSG_TTL)


async def delete_user_message_safely(message: types.Message) -> None:
    """
    Аккуратно удаляет сообщение пользователя с командой, чтобы не засорять чат.

    - Удаляем только в личных чатах (ChatType.PRIVATE), чтобы не ломать историю в группах.
    - Игнорируем ошибки TelegramBadRequest (нет прав, сообщение уже удалено и т.п.).
    """
    # В aiogram message.chat.type — это ChatType, поэтому сравниваем через ==/!=, а не is.
    if message.chat.type != ChatType.PRIVATE:
        return

    try:
        await message.delete()
    except TelegramBadRequest as e:
        logger.debug("Failed to delete user message in chat_id=%s: %s", message.chat.id, e)

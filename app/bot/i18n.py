"""
Локализация бота (ru/en). Язык пользователя хранится в Redis по chat_id.
Если не задан — берётся из Telegram (message.from_user.language_code), иначе fallback на en.
"""
from __future__ import annotations

from app.bot.locales import ALL, DEFAULT_LANG
from app.core.redis import redis_client

# Ключ Redis: последнее сохранённое предпочтение языка для чата. TTL 90 дней — не храним вечно.
USER_LANG_KEY = "bot:user_lang:{chat_id}"
USER_LANG_TTL_SEC = 90 * 24 * 3600


async def get_user_lang(chat_id: int, telegram_language_code: str | None) -> str:
    """
    Возвращает код языка для чата: сначала из Redis (если пользователь уже выбирал /lang),
    иначе из telegram_language_code (ru -> ru, en/en-US/... -> en), иначе DEFAULT_LANG.
    Ограничиваем только поддерживаемыми языками — защита от подстановки несуществующего ключа.
    """
    saved = await redis_client.get(USER_LANG_KEY.format(chat_id=chat_id))
    if saved and saved in ALL:
        return saved
    if telegram_language_code and telegram_language_code.lower().startswith("ru"):
        return "ru"
    if telegram_language_code and telegram_language_code.lower().startswith("en"):
        return "en"
    return DEFAULT_LANG


async def set_user_lang(chat_id: int, lang: str) -> None:
    """Сохраняет выбранный язык в Redis. Вызывать после /lang или смены языка."""
    if lang not in ALL:
        return
    key = USER_LANG_KEY.format(chat_id=chat_id)
    await redis_client.set(key, lang)
    await redis_client.expire(key, USER_LANG_TTL_SEC)


def t(key: str, lang: str, **kwargs: str | int) -> str:
    """
    Возвращает строку по ключу для языка. kwargs подставляются в строку как .format(**kwargs).
    Если ключ или язык отсутствуют — возвращаем ключ, чтобы не падать и было видно в логах.
    """
    strings = ALL.get(lang) or ALL.get(DEFAULT_LANG) or {}
    template = strings.get(key)
    if template is None:
        return key
    try:
        return template.format(**kwargs)
    except KeyError:
        return template

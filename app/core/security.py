from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


_API_KEY: Optional[str] = (
    settings.API_KEY.get_secret_value() if settings.API_KEY is not None else None
)
_API_KEY_HEADER_NAME = settings.API_KEY_HEADER_NAME

api_key_header = APIKeyHeader(name=_API_KEY_HEADER_NAME, auto_error=False)


async def enforce_api_key(api_key: Optional[str] = Depends(api_key_header)) -> None:
    """
    Простейшая проверка API‑ключа.

    - Если API_KEY не задан в настройках, проверка отключена (режим разработки).
    - Если задан, каждый запрос должен передавать корректный ключ в заголовке.
    """

    if _API_KEY is None:
        # Авторизация выключена — ничего не проверяем.
        return

    if not api_key or api_key != _API_KEY:
        logger.warning("Отказ в доступе: некорректный API‑ключ")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


SYMBOL_REGEX = re.compile(r"^[A-Z0-9]{4,20}$")


def validate_symbol(symbol: str) -> str:
    """
    Валидация тикера торговой пары.

    Разрешаем только латинские буквы и цифры, длина от 4 до 20 символов.
    """

    normalized = symbol.upper()
    if not SYMBOL_REGEX.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid symbol format",
        )
    return normalized


async def rate_limit(request: Request) -> None:
    """
    Простое ограничение частоты запросов на уровне IP.

    - Счётчик в Redis с TTL окна (RATE_LIMIT_WINDOW_SECONDS).
    - Если количество запросов превышает RATE_LIMIT_REQUESTS, возвращаем 429.
    """

    if not settings.RATE_LIMIT_ENABLED:
        return

    client_ip = request.client.host if request.client else "unknown"
    key = f"rate:{client_ip}"

    current = await redis_client.incr(key)
    if current == 1:
        # Устанавливаем TTL только при первом инкременте
        await redis_client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)

    if current > settings.RATE_LIMIT_REQUESTS:
        logger.warning("Превышен лимит запросов для IP %s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, slow down",
        )


from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """
    Возвращает singleton‑клиент Redis для всего приложения.

    Используем lru_cache, чтобы не создавать новый клиент на каждый импорт.
    Подключение берётся из REDIS_URL в настройках.
    """

    return redis.from_url(
        settings.REDIS_URL,
        db=0,
        decode_responses=True,
    )


redis_client = get_redis_client()


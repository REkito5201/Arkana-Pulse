from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

import httpx

from app.core.redis import redis_client


class FearGreedPayload(TypedDict, total=False):
    value: int
    classification: str
    timestamp: int


class FearGreedService:
    """
    Сервис для получения индекса страха и жадности.

    - Хранит последнюю полученную ценность в Redis с коротким TTL.
    - При ошибках внешнего API возвращает None, чтобы не ломать основной поток.
    """

    API_URL = "https://api.alternative.me/fng/"
    CACHE_KEY = "fear_greed:latest"
    CACHE_TTL_SECONDS = 300

    @classmethod
    async def get_latest(cls) -> FearGreedPayload | None:
        """Возвращает последний индекс из кэша или внешнего API."""
        # 1. Пытаемся взять данные из Redis
        cached = await redis_client.get(cls.CACHE_KEY)
        if cached:
            try:
                value, classification, ts = cached.split("|", maxsplit=2)
                return FearGreedPayload(
                    value=int(value),
                    classification=classification,
                    timestamp=int(ts),
                )
            except Exception:
                # Если кэш повреждён — просто игнорируем и перезапрашиваем
                pass

        # 2. Идём во внешний API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(cls.API_URL, params={"limit": 1})
                response.raise_for_status()
                data: dict[str, Any] = response.json()
        except Exception:
            return None

        items = data.get("data") or []
        if not items:
            return None

        raw = items[0]
        try:
            value = int(raw["value"])
            classification = str(raw["value_classification"])
            timestamp = int(raw.get("timestamp") or datetime.utcnow().timestamp())
        except Exception:
            return None

        payload: FearGreedPayload = FearGreedPayload(
            value=value,
            classification=classification,
            timestamp=timestamp,
        )

        # 3. Кладём в Redis для последующего быстрого доступа
        cache_value = f"{payload['value']}|{payload['classification']}|{payload['timestamp']}"
        await redis_client.setex(cls.CACHE_KEY, cls.CACHE_TTL_SECONDS, cache_value)

        return payload


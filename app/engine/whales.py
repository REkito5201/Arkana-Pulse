import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Literal

from app.core.redis import redis_client


logger = logging.getLogger(__name__)

WhaleDirection = Literal["in", "out"]


@dataclass(slots=True)
class WhaleAddress:
    """Отслеживаемый адрес кита."""

    address: str
    chain: str
    label: str | None = None


@dataclass(slots=True)
class WhaleEvent:
    """Нормализованное событие крупного движения средств."""

    tx_hash: str
    address: str
    chain: str
    direction: WhaleDirection
    token_symbol: str
    token_address: str
    amount: float
    amount_usd: float
    timestamp: int
    label: str | None = None


class WhaleTrackerService:
    """
    Сервис управления кошельками китов и событиями.

    Отвечает только за хранение и выдачу данных:
    - список отслеживаемых адресов хранится в Redis;
    - события крупных транзакций складываются в Redis‑очередь с ограничением длины.
    """

    ADDRESSES_KEY = "whales:addresses"
    EVENTS_KEY = "whales:events"
    MAX_EVENTS = 200

    async def add_address(self, addr: WhaleAddress) -> None:
        """
        Добавляет или обновляет отслеживаемый адрес.

        Ключ формируем как chain:address в нижнем регистре, чтобы избежать дубликатов.
        Метаданные адреса хранятся в отдельном хеше.
        """
        key = f"{addr.chain}:{addr.address.lower()}"
        payload = {
            "address": addr.address,
            "chain": addr.chain,
            "label": addr.label or "",
        }
        await redis_client.sadd(self.ADDRESSES_KEY, key)
        await redis_client.hset(f"whales:addr:{key}", mapping=payload)

    async def list_addresses(self) -> List[WhaleAddress]:
        """Возвращает все отслеживаемые адреса из Redis."""
        keys = await redis_client.smembers(self.ADDRESSES_KEY)
        items: List[WhaleAddress] = []

        for key in keys:
            meta = await redis_client.hgetall(f"whales:addr:{key}")
            if not meta:
                continue
            items.append(
                WhaleAddress(
                    address=meta.get("address", ""),
                    chain=meta.get("chain", ""),
                    label=meta.get("label") or None,
                )
            )
        return items

    async def push_event(self, event: WhaleEvent) -> None:
        """
        Сохраняет событие в Redis‑очередь с ограничением длины.

        Предполагается, что этот метод вызывается фоновым воркером,
        который слушает внешний API аналитики блокчейна.
        """
        payload = {
            "tx_hash": event.tx_hash,
            "address": event.address,
            "chain": event.chain,
            "direction": event.direction,
            "token_symbol": event.token_symbol,
            "token_address": event.token_address,
            "amount": event.amount,
            "amount_usd": event.amount_usd,
            "timestamp": event.timestamp,
            "label": event.label or "",
        }

        data = json.dumps(payload, ensure_ascii=False)
        await redis_client.lpush(self.EVENTS_KEY, data)
        await redis_client.ltrim(self.EVENTS_KEY, 0, self.MAX_EVENTS - 1)

    async def get_recent_events(self, limit: int = 50) -> List[WhaleEvent]:
        """
        Возвращает последние N событий по кошелькам китов.

        Защищаемся от некорректных данных: битые JSON‑строки и неверные типы
        полей аккуратно пропускаем или приводим к safe‑значениям.
        """
        limit = max(1, min(limit, self.MAX_EVENTS))
        raw_items = await redis_client.lrange(self.EVENTS_KEY, 0, limit - 1)

        events: List[WhaleEvent] = []
        for raw in raw_items:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Failed to decode whale event JSON: %s", raw)
                continue

            ts = payload.get("timestamp")
            if not isinstance(ts, int):
                try:
                    ts = int(ts)
                except (TypeError, ValueError):
                    ts = int(datetime.now(tz=timezone.utc).timestamp())

            try:
                amount = float(payload.get("amount", 0.0) or 0.0)
                amount_usd = float(payload.get("amount_usd", 0.0) or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
                amount_usd = 0.0

            direction = payload.get("direction") or "in"
            if direction not in ("in", "out"):
                direction = "in"

            events.append(
                WhaleEvent(
                    tx_hash=payload.get("tx_hash", ""),
                    address=payload.get("address", ""),
                    chain=payload.get("chain", ""),
                    direction=direction,  # type: ignore[arg-type]
                    token_symbol=payload.get("token_symbol", ""),
                    token_address=payload.get("token_address", ""),
                    amount=amount,
                    amount_usd=amount_usd,
                    timestamp=ts,
                    label=payload.get("label") or None,
                )
            )

        return events


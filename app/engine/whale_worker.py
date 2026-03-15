import asyncio
import logging
from typing import Iterable, List, Union

import aiohttp

from app.core.config import settings
from app.engine.whales import WhaleAddress, WhaleEvent, WhaleTrackerService, WhaleDirection
from app.engine.whale_explorers import ExplorerWhaleClient


logger = logging.getLogger(__name__)


class WhaleApiClient:
    """
    Клиент к внешнему API, который отдаёт события по кошелькам китов.

    Этот класс умышленно сделан максимально простым и независимым. Он ожидает,
    что провайдер вернёт JSON вида:

    {
      "events": [
        {
          "tx_hash": "...",
          "direction": "in" | "out",
          "token_symbol": "USDT",
          "token_address": "0x...",
          "amount": 12345.67,
          "amount_usd": 123456.78,
          "timestamp": 1700000000
        },
        ...
      ]
    }

    Конкретный URL и ключ задаются через настройки:
    - WHALE_API_URL (обязателен для реальной работы);
    - WHALE_API_KEY (опционально, если провайдер требует авторизацию).
    """

    def __init__(self, base_url: str | None, api_key: str | None, timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key
        self.timeout = timeout

    async def fetch_events_for_address(
        self,
        session: aiohttp.ClientSession,
        addr: WhaleAddress,
        min_usd: float,
    ) -> List[WhaleEvent]:
        """
        Загружает события для одного адреса.

        Если базовый URL не задан, возвращает пустой список и пишет предупреждение
        в лог — это безопасный режим по умолчанию.
        """
        if not self.base_url:
            logger.warning("WHALE_API_URL is not configured; skipping whale polling")
            return []

        params = {
            "address": addr.address,
            "chain": addr.chain,
            "minUsd": str(min_usd),
        }
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/events"

        try:
            async with session.get(url, params=params, headers=headers, timeout=self.timeout) as resp:
                if resp.status != 200:
                    logger.warning("Whale API HTTP %s for %s on %s", resp.status, addr.address, addr.chain)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Whale API timeout for %s on %s", addr.address, addr.chain)
            return []
        except Exception:
            logger.exception("Whale API error for %s on %s", addr.address, addr.chain)
            return []

        raw_events = data.get("events") or []
        events: List[WhaleEvent] = []

        for item in raw_events:
            try:
                direction: WhaleDirection = "in" if item.get("direction") == "in" else "out"
                tx_hash = str(item.get("tx_hash", ""))
                token_symbol = str(item.get("token_symbol", "") or "")
                token_address = str(item.get("token_address", "") or "")
                amount = float(item.get("amount", 0.0) or 0.0)
                amount_usd = float(item.get("amount_usd", 0.0) or 0.0)
                timestamp = int(item.get("timestamp"))
            except (TypeError, ValueError, KeyError):
                # Если событие не удалось распарсить, пропускаем его, но не падаем.
                logger.warning("Skipping malformed whale event item: %s", item)
                continue

            events.append(
                WhaleEvent(
                    tx_hash=tx_hash,
                    address=addr.address,
                    chain=addr.chain,
                    direction=direction,
                    token_symbol=token_symbol,
                    token_address=token_address,
                    amount=amount,
                    amount_usd=amount_usd,
                    timestamp=timestamp,
                    label=addr.label,
                )
            )

        return events


async def poll_whales_once(
    service: WhaleTrackerService,
    client: Union[WhaleApiClient, ExplorerWhaleClient],
) -> None:
    """Один цикл опроса всех отслеживаемых адресов (эксплореры или custom API)."""
    addresses: Iterable[WhaleAddress] = await service.list_addresses()
    addresses = list(addresses)

    if not addresses:
        logger.info("No whale addresses configured yet; nothing to poll")
        return

    async with aiohttp.ClientSession() as session:
        for addr in addresses:
            events = await client.fetch_events_for_address(
                session,
                addr,
                min_usd=settings.WHALE_MIN_USD,
            )
            for event in events:
                await service.push_event(event)


def _use_explorer_client() -> bool:
    """Есть ли хотя бы один ключ эксплорера для бесплатного провайдера."""
    return bool(
        settings.ETHERSCAN_API_KEY
        or settings.BSCSCAN_API_KEY
        or settings.POLYGONSCAN_API_KEY
    )


async def run_forever() -> None:
    """
    Основной цикл воркера.

    Приоритет: если задан любой ключ эксплорера (ETHERSCAN_API_KEY, BSCSCAN_API_KEY,
    POLYGONSCAN_API_KEY) — используется бесплатный провайдер на базе Etherscan/BscScan/
    PolygonScan. Иначе — кастомный провайдер по WHALE_API_URL (и опционально WHALE_API_KEY).
    Интервал опроса задаётся через WHALE_POLL_INTERVAL_SECONDS.
    """
    service = WhaleTrackerService()
    if _use_explorer_client():
        client: Union[WhaleApiClient, ExplorerWhaleClient] = ExplorerWhaleClient(
            etherscan_api_key=settings.ETHERSCAN_API_KEY,
            bscscan_api_key=settings.BSCSCAN_API_KEY,
            polygonscan_api_key=settings.POLYGONSCAN_API_KEY,
            timeout=10.0,
        )
        logger.info("Whale worker using Explorer provider (Etherscan/BscScan/PolygonScan)")
    elif settings.WHALE_API_URL:
        api_key = settings.WHALE_API_KEY.get_secret_value() if settings.WHALE_API_KEY else None
        client = WhaleApiClient(
            base_url=settings.WHALE_API_URL,
            api_key=api_key,
            timeout=5.0,
        )
        logger.info("Whale worker using custom WHALE_API_URL provider")
    else:
        logger.warning(
            "No whale provider configured: set ETHERSCAN_API_KEY (or BSCSCAN_API_KEY, "
            "POLYGONSCAN_API_KEY) or WHALE_API_URL in .env"
        )
        return
    interval = max(10, int(settings.WHALE_POLL_INTERVAL_SECONDS))
    logger.info("Starting whale worker with interval %s seconds", interval)

    while True:
        try:
            await poll_whales_once(service, client)
        except Exception:
            logger.exception("Unexpected error in whale worker loop")
        await asyncio.sleep(interval)


def main() -> None:
    """Точка входа для запуска воркера как скрипта."""
    logging.basicConfig(level=settings.LOG_LEVEL)
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()


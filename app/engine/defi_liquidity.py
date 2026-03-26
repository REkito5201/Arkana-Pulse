import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DefiPool:
    """Информация по одному пулу ликвидности."""

    chain: str
    dex: str
    pair_address: str
    base_symbol: str
    base_address: str
    quote_symbol: str
    quote_address: str
    price_usd: float
    liquidity_usd: float
    volume24h_usd: float


class DefiLiquidityService:
    """
    Сервис для получения базовой информации о ликвидности DeFi через публичный API Dexscreener.

    Best practices:
    - используем только публичный API (без ключей), чтобы не тянуть секреты в конфиг;
    - чётко валидируем и нормализуем ответ провайдера;
    - ограничиваем количество возвращаемых пулов и безопасно обрабатываем ошибки сети.
    """

    BASE_URL = "https://api.dexscreener.com/latest/dex"

    async def _fetch_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Небольшой helper для HTTP‑запросов с логированием ошибок."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=5.0) as resp:
                    if resp.status != 200:
                        logger.warning("DeFi API HTTP %s for %s params=%s", resp.status, url, params)
                        return None
                    return await resp.json()
        except Exception:
            logger.exception("DeFi API network error for %s params=%s", url, params)
            return None

    async def search_pools(self, query: str, limit: int = 10) -> list[DefiPool]:
        """
        Ищет пулы ликвидности по символу токена или его адресу.

        Под капотом использует Dexscreener /search, который принимает как символьный тикер,
        так и адрес токена или пары.
        """
        url = f"{self.BASE_URL}/search"
        data = await self._fetch_json(url, params={"q": query})
        if not data:
            return []

        pairs = data.get("pairs") or []
        pools: list[DefiPool] = []

        for item in pairs:
            try:
                chain = str(item.get("chainId", "") or "")
                dex = str(item.get("dexId", "") or "")
                pair_address = str(item.get("pairAddress", "") or "")

                base = item.get("baseToken") or {}
                quote = item.get("quoteToken") or {}

                base_symbol = str(base.get("symbol", "") or "")
                base_address = str(base.get("address", "") or "")
                quote_symbol = str(quote.get("symbol", "") or "")
                quote_address = str(quote.get("address", "") or "")

                # Dexscreener отдаёт цену базового токена в quote, но часто есть и priceUsd.
                price_usd = float(item.get("priceUsd") or 0.0)
                liquidity_usd = float((item.get("liquidity") or {}).get("usd") or 0.0)
                volume24h_usd = float((item.get("volume") or {}).get("h24") or 0.0)
            except (TypeError, ValueError):
                logger.warning("Skipping malformed DeFi pool item: %s", item)
                continue

            if liquidity_usd <= 0:
                # Смысла в пулах без ликвидности нет.
                continue

            pools.append(
                DefiPool(
                    chain=chain,
                    dex=dex,
                    pair_address=pair_address,
                    base_symbol=base_symbol,
                    base_address=base_address,
                    quote_symbol=quote_symbol,
                    quote_address=quote_address,
                    price_usd=price_usd,
                    liquidity_usd=liquidity_usd,
                    volume24h_usd=volume24h_usd,
                )
            )

        # Сортируем по ликвидности и ограничиваем количество результатов.
        pools.sort(key=lambda p: p.liquidity_usd, reverse=True)
        return pools[: max(1, min(limit, 50))]


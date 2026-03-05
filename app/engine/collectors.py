import logging

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


class ExchangeCollector:
    """
    Класс для сбора данных.
    Отвечает только за сетевое взаимодействие (Принцип SRP).
    """

    def __init__(self) -> None:
        # Базовый URL Binance API для получения свечей (Klines)
        self.base_url = "https://api.binance.com/api/v3/klines"

    async def fetch_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> list | None:
        """
        Запрашивает свечи (OHLCV) у биржи.
        symbol: торговая пара (например, BTCUSDT)
        interval: таймфрейм (1m, 5m, 1h, 1d)
        limit: количество последних свечей
        """

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        # Используем асинхронную сессию для запроса
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Binance возвращает много лишнего.
                        # Берём первые 6 элементов: [Open time, Open, High, Low, Close, Volume]
                        return [candle[:6] for candle in data]

                    logger.warning(
                        "Ошибка Binance API (%s): статус %s", symbol, response.status
                    )
                    return None
            except Exception:
                logger.exception("Ошибка сети при запросе %s", symbol)
                return None
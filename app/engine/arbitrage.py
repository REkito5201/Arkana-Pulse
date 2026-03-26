import asyncio
import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Ticker:
    """Нормализованный тикер с разных бирж."""

    exchange: str
    symbol: str
    price: float


@dataclass(slots=True)
class ArbitrageOpportunity:
    """Результат поиска арбитражной возможности для одной пары."""

    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_abs: float
    spread_pct: float


class ArbitrageService:
    """
    Сервис для поиска простого арбитража между биржами.

    Best practice'ы:
    - чёткое разделение ответственности: этот класс только считает и ходит в публичные API;
    - минимальная зависимость от конфигурации (список бирж пока захардкожен, но в одном месте);
    - явные таймауты и обработка ошибок сети;
    - защищаемся от недостоверных данных (price <= 0, NaN).
    """

    BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
    BYBIT_TICKER_URL = "https://api.bybit.com/v5/market/tickers"
    OKX_TICKER_URL = "https://www.okx.com/api/v5/market/ticker"

    def __init__(self, http_timeout: float = 3.0) -> None:
        self.http_timeout = http_timeout

    async def _fetch_json(self, session: aiohttp.ClientSession, url: str, params: dict) -> dict | None:
        """Общий безопасный helper для HTTP‑запросов."""
        try:
            async with session.get(url, params=params, timeout=self.http_timeout) as resp:
                if resp.status != 200:
                    logger.warning("Arbitrage HTTP %s %s: %s", url, params, resp.status)
                    return None
                return await resp.json()
        except TimeoutError:
            logger.warning("Arbitrage timeout %s %s", url, params)
            return None
        except Exception:
            logger.exception("Arbitrage network error %s %s", url, params)
            return None

    async def _fetch_binance_ticker(self, session: aiohttp.ClientSession, symbol: str) -> Ticker | None:
        data = await self._fetch_json(session, self.BINANCE_TICKER_URL, {"symbol": symbol.upper()})
        if not data or "price" not in data:
            return None
        try:
            price = float(data["price"])
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        return Ticker(exchange="binance", symbol=symbol.upper(), price=price)

    async def _fetch_bybit_ticker(self, session: aiohttp.ClientSession, symbol: str) -> Ticker | None:
        # Bybit ожидает пары без слэша, аналогично Binance (BTCUSDT).
        data = await self._fetch_json(
            session,
            self.BYBIT_TICKER_URL,
            {"category": "linear", "symbol": symbol.upper()},
        )
        if not data or "result" not in data:
            return None
        tickers = data.get("result", {}).get("list") or []
        if not tickers:
            return None
        first = tickers[0]
        try:
            price = float(first["lastPrice"])
        except (TypeError, ValueError, KeyError):
            return None
        if price <= 0:
            return None
        return Ticker(exchange="bybit", symbol=symbol.upper(), price=price)

    async def _fetch_okx_ticker(self, session: aiohttp.ClientSession, symbol: str) -> Ticker | None:
        # OKX использует формат BTC-USDT, поэтому аккуратно трансформируем символ.
        base = symbol[:-4]
        quote = symbol[-4:]
        okx_symbol = f"{base}-{quote}"
        data = await self._fetch_json(
            session,
            self.OKX_TICKER_URL,
            {"instId": okx_symbol},
        )
        if not data or "data" not in data:
            return None
        rows = data.get("data") or []
        if not rows:
            return None
        first = rows[0]
        try:
            price = float(first["last"])
        except (TypeError, ValueError, KeyError):
            return None
        if price <= 0:
            return None
        return Ticker(exchange="okx", symbol=symbol.upper(), price=price)

    async def fetch_tickers(self, symbol: str) -> list[Ticker]:
        """
        Параллельно запрашивает цену пары на нескольких биржах.

        Возвращает только валидные тикеры (цена > 0). Ошибки сети логируются,
        но не прерывают выполнение.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_binance_ticker(session, symbol),
                self._fetch_bybit_ticker(session, symbol),
                self._fetch_okx_ticker(session, symbol),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        tickers: list[Ticker] = []
        for res in results:
            if isinstance(res, Exception):
                logger.exception("Arbitrage task raised: %s", res)
                continue
            if res is None:
                continue
            tickers.append(res)
        return tickers

    @staticmethod
    def find_opportunity(symbol: str, tickers: list[Ticker], min_spread_pct: float = 0.1) -> ArbitrageOpportunity | None:
        """
        Ищет простейший арбитраж «купи на X, продай на Y».

        min_spread_pct: минимальный спред в процентах, при котором считаем
        возможность интересной (по умолчанию 0.1%).
        """
        if len(tickers) < 2:
            return None

        # Лучшая цена покупки (минимальная) и лучшая цена продажи (максимальная).
        best_buy = min(tickers, key=lambda t: t.price)
        best_sell = max(tickers, key=lambda t: t.price)

        if best_sell.price <= 0 or best_buy.price <= 0:
            return None

        spread_abs = best_sell.price - best_buy.price
        spread_pct = (spread_abs / best_buy.price) * 100

        if spread_pct < min_spread_pct:
            return None

        return ArbitrageOpportunity(
            symbol=symbol.upper(),
            buy_exchange=best_buy.exchange,
            sell_exchange=best_sell.exchange,
            buy_price=best_buy.price,
            sell_price=best_sell.price,
            spread_abs=spread_abs,
            spread_pct=spread_pct,
        )

    async def scan_symbol(self, symbol: str, min_spread_pct: float = 0.1) -> dict:
        """
        Высокоуровневый метод для API: собирает тикеры и считает спред.

        Возвращает сериализуемый dict c:
        - списком всех цен по биржам;
        - лучшей возможностью (если есть).
        """
        tickers = await self.fetch_tickers(symbol)
        opp = self.find_opportunity(symbol, tickers, min_spread_pct=min_spread_pct)

        return {
            "symbol": symbol.upper(),
            "tickers": [
                {"exchange": t.exchange, "symbol": t.symbol, "price": t.price}
                for t in tickers
            ],
            "opportunity": (
                {
                    "symbol": opp.symbol,
                    "buy_exchange": opp.buy_exchange,
                    "sell_exchange": opp.sell_exchange,
                    "buy_price": opp.buy_price,
                    "sell_price": opp.sell_price,
                    "spread_abs": opp.spread_abs,
                    "spread_pct": opp.spread_pct,
                }
                if opp
                else None
            ),
        }


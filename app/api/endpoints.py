import json
from datetime import datetime
from typing import Any, List

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.engine.collectors import ExchangeCollector
from app.engine.scanner import MarketScanner

router = APIRouter()

# Клиент Redis создаётся один раз на процесс и берёт настройки из ENV
redis_client = redis.from_url(
    settings.REDIS_URL,
    db=0,
    decode_responses=True,
)

class RedisService:
    """Сервис для работы с кэшем и алертами."""

    @staticmethod
    async def cache_market_data(symbol: str, price: float, rsi: float) -> None:
        """Кэширует ключевые метрики для быстрого доступа."""
        await redis_client.set(f"price:{symbol}", price)
        await redis_client.set(f"rsi:{symbol}", rsi)

    @staticmethod
    async def process_rsi_alert(symbol: str, rsi: float) -> None:
        """Логика уведомлений при перекупленности."""
        if rsi <= 70:
            return

        lock_key = f"alert_lock:{symbol}:high"
        if await redis_client.get(lock_key):
            return

        alert_msg = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "rsi": round(rsi, 2),
            "type": "OVERBOUGHT",
        }
        await redis_client.lpush("trading_alerts", json.dumps(alert_msg))
        await redis_client.ltrim("trading_alerts", 0, 19)
        await redis_client.setex(lock_key, 300, "locked")


def format_indicator_series(series: List[Any], precision: int = 2) -> List[float]:
    """
    Вспомогательная функция для очистки данных (DRY).
    Превращает null/NaN в 0.0 и округляет значения.
    """
    return [round(float(x), precision) if x is not None else 0.0 for x in series]


@router.get("/candles/{symbol}")
async def get_historical_candles(symbol: str) -> dict[str, Any]:
    """Возвращает полный пакет данных для графиков (Свечи + BB + MACD + RSI)."""
    symbol = symbol.upper()
    collector = ExchangeCollector()
    scanner = MarketScanner()

    # Получаем сырые данные из коллектора
    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    # Анализируем через Polars
    df = scanner.analyze_assets(raw_data)

    # Приводим индикаторы к чистым числовым рядам
    rsi_series = format_indicator_series(df["rsi"].to_list())
    bb_upper = format_indicator_series(df["bb_upper"].to_list())
    bb_mid = format_indicator_series(df["bb_mid"].to_list())
    bb_lower = format_indicator_series(df["bb_lower"].to_list())
    macd_line = format_indicator_series(df["macd_line"].to_list(), precision=4)
    macd_signal = format_indicator_series(df["macd_signal"].to_list(), precision=4)
    macd_hist = format_indicator_series(df["macd_hist"].to_list(), precision=4)

    # Текущие значения для кэша и сигналов
    current_rsi = rsi_series[-1] if rsi_series else 50.0
    closes = df["close"].to_list()
    current_price = float(closes[-1]) if closes else 0.0

    # 1. Интеграция с Redis
    await RedisService.cache_market_data(symbol, current_price, current_rsi)
    await RedisService.process_rsi_alert(symbol, current_rsi)

    # 2. Формирование ответа (плоский контракт под фронт + вложенный блок indicators)
    candles_payload = [
        {
            "time": int(c[0] / 1000),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
        }
        for c in raw_data
    ]

    summary = scanner.get_signal(df)

    return {
        "symbol": symbol,
        "candles": candles_payload,
        # Плоские поля, которые ожидает фронтенд
        "rsi": current_rsi,
        "rsi_history": rsi_series,
        "bb_upper": bb_upper,
        "bb_middle": bb_mid,
        "bb_lower": bb_lower,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        # Вложенная структура для возможного дальнейшего использования
        "indicators": {
            "rsi": rsi_series,
            "bollinger": {
                "upper": bb_upper,
                "mid": bb_mid,
                "lower": bb_lower,
            },
            "macd": {
                "line": macd_line,
                "signal": macd_signal,
                "hist": macd_hist,
            },
        },
        "summary": summary,
    }

@router.get("/signal/{symbol}")
async def get_crypto_signal(symbol: str) -> dict[str, Any]:
    """Быстрый эндпоинт только для вердикта."""
    symbol = symbol.upper()
    collector = ExchangeCollector()
    scanner = MarketScanner()

    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    df = scanner.analyze_assets(raw_data)
    return scanner.get_signal(df)
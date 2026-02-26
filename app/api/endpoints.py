import json
import redis.asyncio as redis
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException

from app.engine.collectors import ExchangeCollector
from app.engine.scanner import MarketScanner

router = APIRouter()

# Конфигурация Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379

redis_client = redis.Redis(
    host=REDIS_HOST, 
    port=REDIS_PORT, 
    db=0, 
    decode_responses=True
)

class RedisService:
    """Сервис для работы с кэшем и алертами[cite: 19]."""
    
    @staticmethod
    async def cache_market_data(symbol: str, price: float, rsi: float) -> None:
        """Кэширует ключевые метрики для быстрого доступа."""
        await redis_client.set(f"price:{symbol}", price)
        await redis_client.set(f"rsi:{symbol}", rsi)

    @staticmethod
    async def process_rsi_alert(symbol: str, rsi: float) -> None:
        """Логика уведомлений при перекупленности[cite: 13]."""
        if rsi > 70:
            lock_key = f"alert_lock:{symbol}:high"
            if not await redis_client.get(lock_key):
                alert_msg = {
                    "timestamp": datetime.now().isoformat(),
                    "symbol": symbol,
                    "rsi": round(rsi, 2),
                    "type": "OVERBOUGHT"
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
async def get_historical_candles(symbol: str) -> Dict[str, Any]:
    """Возвращает полный пакет данных для графиков (Свечи + BB + MACD + RSI)."""
    symbol = symbol.upper()
    collector = ExchangeCollector()
    scanner = MarketScanner()

    # Получаем сырые данные из коллектора
    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    # Анализируем через Polars [cite: 14]
    df = scanner.analyze_assets(raw_data)
    
    # Извлекаем последние значения для кэша и сигналов
    last_row = df.tail(1).to_dicts()[0]
    current_rsi = last_row.get("rsi", 50.0)
    current_price = last_row.get("close", 0.0)
    
    # 1. Интеграция с Redis
    await RedisService.cache_market_data(symbol, current_price, current_rsi)
    await RedisService.process_rsi_alert(symbol, current_rsi)
    
    # 2. Формирование ответа
    return {
        "symbol": symbol,
        "candles": [
            {
                "time": int(c[0] / 1000),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4])
            } for c in raw_data
        ],
        "indicators": {
            "rsi": format_indicator_series(df["rsi"].to_list()),
            "bollinger": {
                "upper": format_indicator_series(df["bb_upper"].to_list()),
                "mid": format_indicator_series(df["bb_mid"].to_list()),
                "lower": format_indicator_series(df["bb_lower"].to_list())
            },
            "macd": {
                "line": format_indicator_series(df["macd_line"].to_list(), 4),
                "signal": format_indicator_series(df["macd_signal"].to_list(), 4),
                "hist": format_indicator_series(df["macd_hist"].to_list(), 4)
            }
        },
        "summary": scanner.get_signal(df)
    }

@router.get("/signal/{symbol}")
async def get_crypto_signal(symbol: str) -> Dict[str, Any]:
    """Быстрый эндпоинт только для вердикта."""
    symbol = symbol.upper()
    collector = ExchangeCollector()
    scanner = MarketScanner()

    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    df = scanner.analyze_assets(raw_data)
    return scanner.get_signal(df)
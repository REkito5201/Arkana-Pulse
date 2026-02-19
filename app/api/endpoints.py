from fastapi import APIRouter, HTTPException
from app.engine.collectors import ExchangeCollector
from app.engine.scanner import MarketScanner

# Router - это как пульт управления нашими ссылками
router = APIRouter()

@router.get("/signal/{symbol}")
async def get_crypto_signal(symbol: str):
    """
    Принимает тикер (например, BTCUSDT) и возвращает анализ.
    """
    collector = ExchangeCollector()
    scanner = MarketScanner()

    # Запрашиваем данные (теперь символ берётся из ссылки)
    raw_data = await collector.fetch_klines(symbol=symbol.upper())

    if not raw_data:
        raise HTTPException(status_code=404, detail="Symbol not found or Binance API error")
    
    # Прогоняем через наш Polars-движок
    df = scanner.analyze_assets(raw_data)
    signal = scanner.get_signal(df)

    # FastAPI автоматически превратит этот словарь в JSON для браузера
    return {
        "symbol": symbol.upper(),
        "price": signal["price"],
        "rsi": signal["rsi"],
        "signal": signal["signal"]
    }

@router.get("/candles/{symbol}")
async def get_historical_candles(symbol: str):
    collector = ExchangeCollector()
    scanner = MarketScanner()

    # Получаем сырые данные с биржи (обычно это последние 100-500 свечей)
    raw_data = await collector.fetch_klines(symbol=symbol.upper())
    if not raw_data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    # Считаем RSI через Polars
    df = scanner.analyze_assets(raw_data)
    current_rsi = float(df["rsi"].tail(1).item()) # Берём последнее значение
    
    # Форматируем данные специально для TradingView Lightweight Charts
    # Им нужны поля: time (в секундах или YYYY-MM-DD), open, high, low, close
    formatted_candles = []
    for candle in raw_data:
        formatted_candles.append({
            "time": int(candle[0] / 1000), # Конвертируем миллисекунды Binance в секунды Unix
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4])
        })
    
    return {
        "candles": formatted_candles,
        "rsi": round(current_rsi, 2)
    }
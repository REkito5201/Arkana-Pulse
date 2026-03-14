import json
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import enforce_api_key, rate_limit, validate_symbol
from app.engine.collectors import ExchangeCollector
from app.engine.fear_greed import FearGreedService
from app.engine.scanner import MarketScanner
from app.engine.arbitrage import ArbitrageService
from app.engine.whales import WhaleAddress, WhaleTrackerService
from app.engine.defi_liquidity import DefiLiquidityService

router = APIRouter(
    dependencies=[Depends(enforce_api_key), Depends(rate_limit)],
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
    Подходит для индикаторов, где нули в начале ряда не искажают шкалу.
    """
    return [round(float(x), precision) if x is not None else 0.0 for x in series]


def format_indicator_series_nullable(
    series: List[Any], precision: int = 2
) -> List[float | None]:
    """
    Форматирование для индикаторов, где 0.0 — некорректная замена NaN.
    Возвращает None для пустых значений, чтобы фронтенд видел разрывы в серии,
    а не рисовал линии на нулевой цене (актуально для Ichimoku).
    """
    formatted: List[float | None] = []
    for value in series:
        if value is None:
            formatted.append(None)
        else:
            try:
                formatted.append(round(float(value), precision))
            except (TypeError, ValueError):
                formatted.append(None)
    return formatted


@router.get("/candles/{symbol}")
async def get_historical_candles(symbol: str = Depends(validate_symbol)) -> dict[str, Any]:
    """Возвращает полный пакет данных для графиков (Свечи + BB + MACD + RSI)."""
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

    ichi_conversion = (
        format_indicator_series_nullable(df["ichi_conversion"].to_list())
        if "ichi_conversion" in df.columns
        else []
    )
    ichi_base = (
        format_indicator_series_nullable(df["ichi_base"].to_list())
        if "ichi_base" in df.columns
        else []
    )
    ichi_span_a = (
        format_indicator_series_nullable(df["ichi_span_a"].to_list())
        if "ichi_span_a" in df.columns
        else []
    )
    ichi_span_b = (
        format_indicator_series_nullable(df["ichi_span_b"].to_list())
        if "ichi_span_b" in df.columns
        else []
    )

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
    fear_greed = await FearGreedService.get_latest()

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
        "ichi_conversion": ichi_conversion,
        "ichi_base": ichi_base,
        "ichi_span_a": ichi_span_a,
        "ichi_span_b": ichi_span_b,
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
        "ichimoku": {
            "conversion": ichi_conversion,
            "base": ichi_base,
            "span_a": ichi_span_a,
            "span_b": ichi_span_b,
        },
        "summary": summary,
        "fear_greed": fear_greed,
    }

@router.get("/signal/{symbol}")
async def get_crypto_signal(symbol: str = Depends(validate_symbol)) -> dict[str, Any]:
    """Быстрый эндпоинт только для вердикта."""
    collector = ExchangeCollector()
    scanner = MarketScanner()

    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    df = scanner.analyze_assets(raw_data)
    return scanner.get_signal(df)


ARBITRAGE_CACHE_KEY_PREFIX = "arbitrage:"


@router.get("/arbitrage/{symbol}")
async def get_arbitrage_opportunity(
    symbol: str = Depends(validate_symbol),
    min_spread_pct: float = 0.1,
) -> dict[str, Any]:
    """
    Простой поиск кросс‑биржевого арбитража для одной пары.

    Результат кэшируется в Redis на ARBITRAGE_CACHE_TTL_SECONDS секунд,
    чтобы снизить нагрузку на биржи и ускорить повторные запросы.

    min_spread_pct: минимальный процент спреда, при котором возможность
    считается интересной. По умолчанию 0.1%. Фильтр применяется к закэшированным
    данным, без повторного запроса к биржам.
    """
    cache_key = f"{ARBITRAGE_CACHE_KEY_PREFIX}{symbol}"
    ttl = max(10, getattr(settings, "ARBITRAGE_CACHE_TTL_SECONDS", 60))

    cached_raw = await redis_client.get(cache_key)
    if cached_raw:
        try:
            data = json.loads(cached_raw)
        except (json.JSONDecodeError, TypeError):
            data = None
        if isinstance(data, dict) and "tickers" in data:
            opp = data.get("opportunity")
            if (
                min_spread_pct > 0
                and opp is not None
                and isinstance(opp, dict)
                and (opp.get("spread_pct") or 0) < min_spread_pct
            ):
                data = {**data, "opportunity": None}
            return data

    service = ArbitrageService()
    result = await service.scan_symbol(symbol, min_spread_pct=0)
    await redis_client.setex(cache_key, ttl, json.dumps(result))

    opp = result.get("opportunity")
    if (
        min_spread_pct > 0
        and opp is not None
        and isinstance(opp, dict)
        and (opp.get("spread_pct") or 0) < min_spread_pct
    ):
        result = {**result, "opportunity": None}
    return result


class WhaleAddressIn(BaseModel):
    """Входная модель для добавления/обновления адреса кита."""

    address: str
    chain: str
    label: str | None = None


@router.get("/whales/addresses")
async def get_whale_addresses() -> dict[str, Any]:
    """Возвращает список отслеживаемых адресов китов."""
    service = WhaleTrackerService()
    addresses = await service.list_addresses()
    return {
        "items": [
            {
                "address": a.address,
                "chain": a.chain,
                "label": a.label,
            }
            for a in addresses
        ]
    }


@router.post("/whales/addresses")
async def add_whale_address(payload: WhaleAddressIn) -> dict[str, Any]:
    """
    Добавляет новый адрес кита к отслеживанию.

    Эндпоинт защищён общим API‑ключом и rate‑лимитом роутера.
    """
    service = WhaleTrackerService()
    addr = WhaleAddress(
        address=payload.address,
        chain=payload.chain,
        label=payload.label,
    )
    await service.add_address(addr)
    return {"status": "ok"}


@router.get("/whales/events")
async def get_whale_events(
    limit: int = 50,
    direction: str | None = None,
    chain: str | None = None,
    min_usd: float | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    """
    Возвращает последние события по кошелькам китов с опциональной фильтрацией.

    - limit: сколько событий вернуть (1..MAX_EVENTS).
    - direction: "in" | "out" — только входящие или исходящие; без параметра — все.
    - chain: фильтр по сети (например ethereum, bitcoin).
    - min_usd: минимальный объём в USD.
    - symbol: фильтр по тикеру токена (например USDT, ETH).
    """
    service = WhaleTrackerService()
    cap = min(max(1, limit), service.MAX_EVENTS)
    events = await service.get_recent_events(limit=service.MAX_EVENTS)
    if direction and direction.lower() in ("in", "out"):
        events = [e for e in events if e.direction == direction.lower()]
    if chain and chain.strip():
        chain_lo = chain.strip().lower()
        events = [e for e in events if (e.chain or "").lower() == chain_lo]
    if min_usd is not None and min_usd > 0:
        events = [e for e in events if e.amount_usd >= min_usd]
    if symbol and symbol.strip():
        sym_lo = symbol.strip().upper()
        events = [e for e in events if (e.token_symbol or "").upper() == sym_lo]
    events = events[:cap]
    return {
        "items": [
            {
                "tx_hash": e.tx_hash,
                "address": e.address,
                "chain": e.chain,
                "direction": e.direction,
                "token_symbol": e.token_symbol,
                "token_address": e.token_address,
                "amount": e.amount,
                "amount_usd": e.amount_usd,
                "timestamp": e.timestamp,
                "label": e.label,
            }
            for e in events
        ]
    }


@router.get("/defi/liquidity")
async def get_defi_liquidity(
    symbol: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Возвращает базовую информацию о ликвидности DeFi для указанного токена.

    symbol: тикер (BTC, ETH, TON) или адрес токена/пары. Под капотом используется
    публичный API Dexscreener /search, поэтому поддерживаются оба варианта.
    """
    service = DefiLiquidityService()
    # Нормализуем символ: обрезаем общие суффиксы вида USDT/USDC, если пользователь
    # передал торговую пару вроде BTCUSDT. Это best‑effort эвристика.
    base_query = symbol.upper()
    for suffix in ("USDT", "USDC", "USD"):
        if base_query.endswith(suffix) and len(base_query) > len(suffix):
            base_query = base_query[: -len(suffix)]
            break

    pools = await service.search_pools(base_query, limit=limit)
    return {
        "query": base_query,
        "pools": [
            {
                "chain": p.chain,
                "dex": p.dex,
                "pair_address": p.pair_address,
                "base_symbol": p.base_symbol,
                "base_address": p.base_address,
                "quote_symbol": p.quote_symbol,
                "quote_address": p.quote_address,
                "price_usd": p.price_usd,
                "liquidity_usd": p.liquidity_usd,
                "volume24h_usd": p.volume24h_usd,
            }
            for p in pools
        ],
    }
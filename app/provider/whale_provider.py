from __future__ import annotations

"""
HTTP‑провайдер событий китов для воркера.

- Принимает запросы от whale‑worker по внутренней сети Docker.
- Для EVM‑сетей (Ethereum/BSC/Polygon) переиспользует ExplorerWhaleClient.
- Для Bitcoin использует внешний REST‑API (по умолчанию Blockstream), не требующий ключа.

Формат ответа совместим с WhaleApiClient: {"events": [...]}.
"""

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from app.core.config import settings
from app.engine.whale_explorers import ExplorerWhaleClient
from app.engine.whales import WhaleAddress, WhaleEvent


app = FastAPI(title="Whale Provider", version="1.0.0")


def _normalize_chain(chain: str) -> str:
    """
    Нормализация названия сети.

    Внешний API может присылать разные варианты (ETH, ethereum, ETHEREUM и т.п.).
    Для конфигурации и маршрутизации вниз по стеку используем единый формат.
    """

    return (chain or "").strip().lower()


def _require_api_key(authorization: Optional[str] = Header(default=None)) -> None:
    """
    Простейшая проверка авторизации на уровне сервиса.

    - Если WHALE_API_KEY не задан, сервис работает без авторизации (dev‑режим).
    - Если задан, ожидаем заголовок Authorization: Bearer <token>.
    - Токен не логируем и не возвращаем клиенту (DevSecOps: не светим секреты).
    """

    if settings.WHALE_API_KEY is None:
        return

    expected = settings.WHALE_API_KEY.get_secret_value()
    if not expected:
        return

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )


async def _fetch_evm_events(
    address: str,
    chain: str,
    min_usd: float,
) -> List[WhaleEvent]:
    """
    Загружает события по EVM‑сетям через ExplorerWhaleClient.

    Параметры окружения (ключи эксплореров, таймауты) берём из settings — без хардкода.
    """

    client = ExplorerWhaleClient(
        etherscan_api_key=settings.ETHERSCAN_API_KEY,
        bscscan_api_key=settings.BSCSCAN_API_KEY,
        polygonscan_api_key=settings.POLYGONSCAN_API_KEY,
        timeout=10.0,
    )
    addr = WhaleAddress(address=address, chain=chain)

    # Здесь открывается сессия внутри клиента; для упрощения и изоляции
    # провайдера используем его существующую реализацию без переизобретения.
    import aiohttp
    import asyncio

    async with aiohttp.ClientSession() as session:
        return await client.fetch_events_for_address(session, addr, min_usd=min_usd)


async def _fetch_btc_events(
    address: str,
    min_usd: float,
) -> List[WhaleEvent]:
    """
    Загружает события по биткоину через внешний REST‑API.

    По умолчанию используется Blockstream API (BTC_API_BASE_URL), но базовый URL
    переопределяется через переменную окружения и настройки — без жёсткой
    привязки к конкретному провайдеру.
    """

    import aiohttp
    import asyncio
    import time

    base_url = settings.BTC_API_BASE_URL.rstrip("/")
    timeout = aiohttp.ClientTimeout(total=settings.BTC_API_TIMEOUT_SECONDS)

    # Ограничиваем количество анализируемых транзакций, чтобы не преткнуться
    # в лимиты и не тянуть гигантский адресный исторический объём.
    max_txs = settings.BTC_MAX_TXS_PER_ADDRESS

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Список последних транзакций по адресу.
        # Эндпоинт и формат выбираем из документации провайдера; при смене
        # провайдера меняется только BTC_API_BASE_URL и логика разбора ниже.
        txs_url = f"{base_url}/address/{address}/txs"
        async with session.get(txs_url, params={"limit": max_txs}) as resp:
            if resp.status != 200:
                # Не пробрасываем тело ответа в лог, чтобы не засветить лишнее.
                return []
            data = await resp.json()

        events: List[WhaleEvent] = []

        # Курс BTC берём из публичного Binance API (переиспользуем общую логику).
        from app.engine.whale_explorers import _fetch_spot_price  # type: ignore[attr-defined]

        price_btc = await _fetch_spot_price(session, "BTC")
        if not price_btc:
            return []

        # Формат Blockstream API: каждая транзакция содержит списки vin/vout.
        # Нам нужен чистый нетто‑баланс адреса по каждой транзакции.
        for tx in data[:max_txs]:
            txid = str(tx.get("txid") or tx.get("tx_hash") or "")
            if not txid:
                continue

            vins = tx.get("vin") or []
            vouts = tx.get("vout") or []

            value_in_sats = 0
            value_out_sats = 0

            # Суммарный расход адреса в этой транзакции.
            for vin in vins:
                prevout = vin.get("prevout") or {}
                addr_list = prevout.get("scriptpubkey_address")
                if addr_list == address:
                    value_in_sats += int(prevout.get("value", 0))

            # Суммарный приход на адрес в этой транзакции.
            for vout in vouts:
                addr_out = vout.get("scriptpubkey_address")
                if addr_out == address:
                    value_out_sats += int(vout.get("value", 0))

            net_sats = value_out_sats - value_in_sats
            if net_sats == 0:
                continue

            amount_btc = net_sats / 1e8
            direction: str = "in" if net_sats > 0 else "out"
            amount_usd = abs(amount_btc) * price_btc

            if amount_usd < min_usd:
                continue

            ts = int(tx.get("status", {}).get("block_time", time.time()))

            events.append(
                WhaleEvent(
                    tx_hash=txid,
                    address=address,
                    chain="btc",
                    direction=direction,  # type: ignore[arg-type]
                    token_symbol="BTC",
                    token_address="",
                    amount=abs(amount_btc),
                    amount_usd=amount_usd,
                    timestamp=ts,
                    label=None,
                )
            )

        return events


@app.get("/events")
async def get_whale_events(
    address: str = Query(..., min_length=1, description="Адрес кошелька кита"),
    chain: str = Query("ethereum", description="Название сети: ethereum/bsc/polygon/btc и т.п."),
    min_usd: float = Query(0.0, ge=0.0, description="Минимальная сумма события в USD"),
    _: None = Depends(_require_api_key),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Унифицированная точка входа для whale‑worker.

    В зависимости от значения chain делегирует запрос соответствующему
    провайдеру (EVM‑эксплореры или Bitcoin‑API).
    """

    normalized_chain = _normalize_chain(chain)

    if normalized_chain in {"ethereum", "eth", "bsc", "bnb", "polygon", "matic"}:
        events = await _fetch_evm_events(address=address, chain=normalized_chain, min_usd=min_usd)
    elif normalized_chain in {"btc", "bitcoin"}:
        events = await _fetch_btc_events(address=address, min_usd=min_usd)
    else:
        # Не падаем 5xx, а аккуратно сообщаем о неподдерживаемой сети.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chain: {chain}",
        )

    # Преобразуем dataclass в словари, совместимые с ожиданиями WhaleApiClient.
    payload: List[Dict[str, Any]] = []
    for ev in events:
        item = asdict(ev)
        payload.append(
            {
                "tx_hash": item["tx_hash"],
                "direction": item["direction"],
                "token_symbol": item["token_symbol"],
                "token_address": item["token_address"],
                "amount": item["amount"],
                "amount_usd": item["amount_usd"],
                "timestamp": item["timestamp"],
            }
        )

    return {"events": payload}



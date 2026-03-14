"""
Провайдер Whale Alert для событий китов.

Использует REST API Whale Alert: GET {blockchain}/address/{hash}/transactions.
Данные нормализуются в WhaleEvent; направление (in/out) определяется по inputs/outputs.
"""
import logging
from typing import Any, List

import aiohttp

from app.engine.whales import WhaleAddress, WhaleEvent

logger = logging.getLogger(__name__)

WHALE_ALERT_BASE = "https://leviathan.whale-alert.io"

# Маппинг имён сетей приложения на идентификаторы Whale Alert (lowercase).
CHAIN_TO_BLOCKCHAIN: dict[str, str] = {
    "ethereum": "ethereum",
    "eth": "ethereum",
    "bitcoin": "bitcoin",
    "btc": "bitcoin",
    "tron": "tron",
    "trx": "tron",
    "solana": "solana",
    "sol": "solana",
    "polygon": "polygon",
    "matic": "polygon",
    "bnb": "binance",  # BNB Chain
    "binance": "binance",
    "bnbchain": "binance",
    "ripple": "ripple",
    "xrp": "ripple",
    "cardano": "cardano",
    "ada": "cardano",
    "dogecoin": "dogecoin",
    "doge": "dogecoin",
    "litecoin": "litecoin",
    "ltc": "litecoin",
    "bitcoin cash": "bitcoin_cash",
    "bch": "bitcoin_cash",
    "algorand": "algorand",
    "algo": "algorand",
}


def _normalize_chain(chain: str) -> str:
    """Приводит имя сети к формату Whale Alert (lowercase, без пробелов)."""
    key = (chain or "").strip().lower().replace(" ", "")
    return CHAIN_TO_BLOCKCHAIN.get(key, (chain or "ethereum").lower())


def _parse_sub_tx(
    sub: dict[str, Any],
    tx_hash: str,
    timestamp: int,
    our_address: str,
    chain: str,
    label: str | None,
    min_usd: float,
) -> List[WhaleEvent]:
    """
    Парсит одну sub_transaction в список WhaleEvent (один на наш адрес по направлению).

    our_address нормализуется к lowercase для сравнения (EVM); для bitcoin и др. сравниваем как есть.
    """
    symbol = str(sub.get("symbol") or "").strip() or "?"
    unit_price = float(sub.get("unit_price_usd") or 0.0)
    inputs = sub.get("inputs") or []
    outputs = sub.get("outputs") or []
    our_lower = our_address.lower()

    def addr_match(io: dict) -> bool:
        a = (io.get("address") or "").strip()
        if not a:
            return False
        return a.lower() == our_lower or a == our_address

    amount_in = 0.0
    amount_out = 0.0
    for inp in inputs:
        if addr_match(inp):
            try:
                amount_out += float(inp.get("amount") or 0)
            except (TypeError, ValueError):
                pass
    for out in outputs:
        if addr_match(out):
            try:
                amount_in += float(out.get("amount") or 0)
            except (TypeError, ValueError):
                pass

    events: List[WhaleEvent] = []
    if amount_in > 0 and unit_price > 0:
        amount_usd = amount_in * unit_price
        if amount_usd >= min_usd:
            events.append(
                WhaleEvent(
                    tx_hash=tx_hash,
                    address=our_address,
                    chain=chain,
                    direction="in",
                    token_symbol=symbol,
                    token_address="",
                    amount=amount_in,
                    amount_usd=amount_usd,
                    timestamp=timestamp,
                    label=label,
                )
            )
    if amount_out > 0 and unit_price > 0:
        amount_usd = amount_out * unit_price
        if amount_usd >= min_usd:
            events.append(
                WhaleEvent(
                    tx_hash=tx_hash,
                    address=our_address,
                    chain=chain,
                    direction="out",
                    token_symbol=symbol,
                    token_address="",
                    amount=amount_out,
                    amount_usd=amount_usd,
                    timestamp=timestamp,
                    label=label,
                )
            )
    return events


class WhaleAlertClient:
    """
    Клиент Whale Alert REST API.

    Загружает транзакции по адресу и преобразует их в WhaleEvent с фильтром по min_usd.
    """

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def fetch_events_for_address(
        self,
        session: aiohttp.ClientSession,
        addr: WhaleAddress,
        min_usd: float,
        limit: int = 50,
    ) -> List[WhaleEvent]:
        """
        Загружает транзакции по адресу и возвращает события с amount_usd >= min_usd.
        """
        blockchain = _normalize_chain(addr.chain)
        url = f"{WHALE_ALERT_BASE}/{blockchain}/address/{addr.address}/transactions"
        params: dict[str, str | int] = {
            "api_key": self.api_key,
            "limit": min(limit, 256),
            "order": "desc",
        }
        try:
            async with session.get(url, params=params, timeout=self.timeout) as resp:
                if resp.status == 401:
                    logger.warning("Whale Alert API: unauthorized (invalid or missing API key)")
                    return []
                if resp.status == 404:
                    logger.debug("Whale Alert: no data for %s on %s", addr.address, blockchain)
                    return []
                if resp.status != 200:
                    logger.warning(
                        "Whale Alert API HTTP %s for %s on %s",
                        resp.status,
                        addr.address,
                        blockchain,
                    )
                    return []
                data = await resp.json()
        except aiohttp.ClientError as e:
            logger.warning("Whale Alert request failed for %s: %s", addr.address, e)
            return []
        except Exception:
            logger.exception("Whale Alert error for %s on %s", addr.address, blockchain)
            return []

        raw_txs = data.get("transactions") or []
        events: List[WhaleEvent] = []
        for tx in raw_txs:
            tx_hash = str(tx.get("hash") or "")
            try:
                ts = int(tx.get("timestamp") or 0)
            except (TypeError, ValueError):
                ts = 0
            subs = tx.get("sub_transactions") or tx.get("sub_transaction") or []
            if isinstance(subs, dict):
                subs = [subs]
            for sub in subs:
                events.extend(
                    _parse_sub_tx(
                        sub,
                        tx_hash=tx_hash,
                        timestamp=ts,
                        our_address=addr.address,
                        chain=addr.chain,
                        label=addr.label,
                        min_usd=min_usd,
                    )
                )
        return events

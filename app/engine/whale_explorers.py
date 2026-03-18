"""
Провайдер событий китов на базе бесплатных API блокчейн-эксплореров.

Поддерживаются Etherscan (Ethereum), BscScan (BNB Chain), PolygonScan (Polygon).
Используются txlist (нативная монета) и tokentx (ERC-20); курс для USD — публичный
Binance API (без ключа). Лимиты и таймауты соблюдаются (DevSecOps).
"""
import asyncio
import logging
from typing import List, Optional

import aiohttp

from app.engine.whales import WhaleAddress, WhaleEvent

logger = logging.getLogger(__name__)

# Стейблкоины: приблизительный курс 1:1 USD для расчёта amount_usd
STABLECOIN_SYMBOLS = frozenset({"USDT", "USDC", "DAI", "BUSD", "TUSD", "USDP", "FRAX"})

# Конфиг эксплореров: base URL API, имя переменной окружения для ключа, тикер нативной монеты для Binance
EXPLORER_CONFIG: dict[str, dict[str, str]] = {
    "ethereum": {"base": "https://api.etherscan.io", "key_env": "ETHERSCAN_API_KEY", "native": "ETH"},
    "eth": {"base": "https://api.etherscan.io", "key_env": "ETHERSCAN_API_KEY", "native": "ETH"},
    "bsc": {"base": "https://api.bscscan.com", "key_env": "BSCSCAN_API_KEY", "native": "BNB"},
    "bnb": {"base": "https://api.bscscan.com", "key_env": "BSCSCAN_API_KEY", "native": "BNB"},
    "polygon": {"base": "https://api.polygonscan.com", "key_env": "POLYGONSCAN_API_KEY", "native": "MATIC"},
    "matic": {"base": "https://api.polygonscan.com", "key_env": "POLYGONSCAN_API_KEY", "native": "MATIC"},
}

BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"
REQUEST_DELAY_SEC = 0.25  # Соблюдение лимитов эксплореров (≈4 req/s на ключ)


def _normalize_chain(chain: str) -> str:
    """Приводит имя сети к ключу конфига эксплорера."""
    key = (chain or "").strip().lower()
    return key if key in EXPLORER_CONFIG else "ethereum"


def _wei_to_float(wei_str: str) -> float:
    """Конвертирует значение в wei (строка) в человекочитаемое число."""
    try:
        return int(wei_str) / 1e18
    except (ValueError, TypeError):
        return 0.0


def _token_amount(raw: str, decimals: int = 18) -> float:
    """Конвертирует сырое значение токена по decimals."""
    try:
        d = 10 ** min(int(decimals), 18)
        return int(raw) / d
    except (ValueError, TypeError):
        return 0.0


async def _fetch_spot_price(session: aiohttp.ClientSession, symbol: str) -> float:
    """Загружает спотовую цену пары с Binance (публичный API, без ключа)."""
    try:
        async with session.get(
            BINANCE_PRICE_URL,
            params={"symbol": f"{symbol}USDT"},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                return 0.0
            data = await resp.json()
            return float(data.get("price") or 0)
    except Exception as e:
        logger.debug("Spot price fetch failed for %s: %s", symbol, e)
        return 0.0


class ExplorerWhaleClient:
    """
    Клиент к Etherscan-совместимым API (Etherscan, BscScan, PolygonScan).

    Загружает обычные транзакции (txlist) и токен-трансферы (tokentx) по адресу,
    приводит к WhaleEvent, фильтрует по min_usd. Ключи API задаются через
    настройки (опционально; без ключа лимиты эксплореров жёстче).
    """

    def __init__(
        self,
        etherscan_api_key: Optional[str] = None,
        bscscan_api_key: Optional[str] = None,
        polygonscan_api_key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self._api_keys = {
            "ethereum": etherscan_api_key or "",
            "eth": etherscan_api_key or "",
            "bsc": bscscan_api_key or "",
            "bnb": bscscan_api_key or "",
            "polygon": polygonscan_api_key or "",
            "matic": polygonscan_api_key or "",
        }
        self.timeout = timeout
        self._price_cache: dict[str, float] = {}
        self._price_cache_ts: float = 0.0
        self._price_cache_ttl = 60.0  # секунд

    async def _get_native_price(self, session: aiohttp.ClientSession, chain_key: str) -> float:
        """Кэш спотовых цен на один цикл опроса (TTL 60 с)."""
        import time
        now = time.monotonic()
        if now - self._price_cache_ts > self._price_cache_ttl:
            self._price_cache.clear()
            self._price_cache_ts = now
        native = EXPLORER_CONFIG.get(chain_key, {}).get("native", "ETH")
        if native not in self._price_cache:
            self._price_cache[native] = await _fetch_spot_price(session, native)
            await asyncio.sleep(REQUEST_DELAY_SEC)
        return self._price_cache.get(native) or 0.0

    async def fetch_events_for_address(
        self,
        session: aiohttp.ClientSession,
        addr: WhaleAddress,
        min_usd: float,
    ) -> List[WhaleEvent]:
        """
        Загружает транзакции по адресу из эксплорера и возвращает события с amount_usd >= min_usd.
        """
        chain_key = _normalize_chain(addr.chain)
        cfg = EXPLORER_CONFIG.get(chain_key)
        if not cfg:
            logger.warning("Unsupported chain for explorer: %s", addr.chain)
            return []
        base = cfg["base"]
        api_key = self._api_keys.get(chain_key, "")
        native_symbol = cfg["native"]
        our = addr.address.strip().lower()
        events: List[WhaleEvent] = []
        price_native = await self._get_native_price(session, chain_key)

        # Обычные транзакции (нативная монета)
        params: dict[str, str] = {
            "module": "account",
            "action": "txlist",
            "address": addr.address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "50",
            "sort": "desc",
        }
        if api_key:
            params["apikey"] = api_key
        try:
            async with session.get(
                f"{base}/api",
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                await asyncio.sleep(REQUEST_DELAY_SEC)
                if resp.status != 200:
                    logger.warning("Explorer txlist HTTP %s for %s", resp.status, addr.address)
                    return []
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("Explorer txlist timeout for %s", addr.address)
            return []
        except Exception:
            logger.exception("Explorer txlist error for %s", addr.address)
            return []

        result_list = data.get("result")
        if str(data.get("status")) != "1":
            # Некоторые бесплатные/лимитируемые ответы Etherscan могут вернуть
            # status="0" (NOTOK), но при этом содержать непустой `result`.
            # Поэтому фильтруем только тогда, когда `result` пустой/невалидный.
            msg = data.get("message", "Unknown")
            if "rate limit" in str(msg).lower() or "Max rate" in str(msg).lower():
                logger.warning("Explorer rate limit for %s: %s", addr.address, msg)
                return []

            if not isinstance(result_list, list) or len(result_list) == 0:
                return []

        for tx in result_list or []:
            if not isinstance(tx, dict):
                continue
            from_addr = (tx.get("from") or "").strip().lower()
            to_addr = (tx.get("to") or "").strip().lower()
            value_wei = tx.get("value") or "0"
            amount = _wei_to_float(value_wei)
            if amount <= 0:
                continue
            direction: str = "out" if from_addr == our else "in" if to_addr == our else ""
            if not direction:
                continue
            amount_usd = amount * price_native if price_native else 0.0
            if amount_usd < min_usd:
                continue
            try:
                ts = int(tx.get("timeStamp") or 0)
            except (TypeError, ValueError):
                ts = 0
            events.append(
                WhaleEvent(
                    tx_hash=str(tx.get("hash") or ""),
                    address=addr.address,
                    chain=addr.chain,
                    direction=direction,
                    token_symbol=native_symbol,
                    token_address="",
                    amount=amount,
                    amount_usd=amount_usd,
                    timestamp=ts,
                    label=addr.label,
                )
            )

        # Токен-трансферы (ERC-20)
        params_tok = {
            "module": "account",
            "action": "tokentx",
            "address": addr.address,
            "page": "1",
            "offset": "50",
            "sort": "desc",
        }
        if api_key:
            params_tok["apikey"] = api_key
        try:
            async with session.get(
                f"{base}/api",
                params=params_tok,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                await asyncio.sleep(REQUEST_DELAY_SEC)
                if resp.status != 200:
                    return events
                data_tok = await resp.json()
        except Exception:
            return events

        result_tok_list = data_tok.get("result")
        if str(data_tok.get("status")) != "1":
            # Аналогично txlist: допускаем status!="1", если `result` непустой.
            msg = data_tok.get("message", "Unknown")
            if "rate limit" in str(msg).lower() or "Max rate" in str(msg).lower():
                return events
            if not isinstance(result_tok_list, list) or len(result_tok_list) == 0:
                return events

        for tx in result_tok_list or []:
            if not isinstance(tx, dict):
                continue
            from_addr = (tx.get("from") or "").strip().lower()
            to_addr = (tx.get("to") or "").strip().lower()
            direction = "out" if from_addr == our else "in" if to_addr == our else ""
            if not direction:
                continue
            try:
                decimals = int(tx.get("tokenDecimal") or 18)
            except (TypeError, ValueError):
                decimals = 18
            amount = _token_amount(str(tx.get("value") or "0"), decimals)
            if amount <= 0:
                continue
            symbol = (tx.get("tokenSymbol") or "?").strip().upper()
            if symbol in STABLECOIN_SYMBOLS:
                amount_usd = amount
            else:
                amount_usd = 0.0  # Не считаем USD для неизвестных токенов
            if amount_usd > 0 and amount_usd < min_usd:
                continue
            if amount_usd == 0 and min_usd > 0:
                continue  # Токены без цены не проходят порог
            try:
                ts = int(tx.get("timeStamp") or 0)
            except (TypeError, ValueError):
                ts = 0
            events.append(
                WhaleEvent(
                    tx_hash=str(tx.get("hash") or ""),
                    address=addr.address,
                    chain=addr.chain,
                    direction=direction,
                    token_symbol=symbol,
                    token_address=str(tx.get("contractAddress") or ""),
                    amount=amount,
                    amount_usd=amount_usd,
                    timestamp=ts,
                    label=addr.label,
                )
            )

        return events

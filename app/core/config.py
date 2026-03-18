"""
Настройки приложения. Поддержка секретов из переменных окружения или из файлов
(Docker secrets: задайте BOT_TOKEN_FILE=/run/secrets/bot_token и т.д.).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _read_secret_from_file(path: str | Path) -> str:
    """Читает значение секрета из файла (без лишних пробелов и переводов строк)."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


class Settings(BaseSettings):
    # --- Бот ---
    BOT_TOKEN: SecretStr | None = None  # или задайте BOT_TOKEN_FILE=/run/secrets/bot_token
    ADMIN_ID: int = 0

    # --- Биржи ---
    BINANCE_API_KEY: str | None = None
    BINANCE_API_SECRET: SecretStr | None = None

    # --- Внешний API для кошельков китов ---
    # Бесплатные эксплореры (приоритет): ключи с etherscan.io, bscscan.com, polygonscan.com
    ETHERSCAN_API_KEY: str | None = None
    BSCSCAN_API_KEY: str | None = None
    POLYGONSCAN_API_KEY: str | None = None
    # Опционально: кастомный провайдер (если ни один ключ эксплорера не задан)
    WHALE_API_URL: str | None = None
    WHALE_API_KEY: SecretStr | None = None
    WHALE_MIN_USD: float = 100_000.0
    WHALE_POLL_INTERVAL_SECONDS: int = 60

    # --- Провайдер китов (внутренний HTTP‑сервис) ---
    BTC_API_BASE_URL: str = "https://blockstream.info/api"
    BTC_API_TIMEOUT_SECONDS: int = 10
    BTC_MAX_TXS_PER_ADDRESS: int = 50

    # --- Арбитраж: кэш в Redis ---
    ARBITRAGE_CACHE_TTL_SECONDS: int = 60

    # --- Базы данных ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Настройки API и WebApp ---
    PROJECT_NAME: str = "ARKANA PULSE"
    API_V1_STR: str = "/api/v1"
    WEBAPP_URL: str = "http://localhost:8000"

    # --- CORS ---
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # --- API‑ключ ---
    API_KEY: SecretStr | None = None
    API_KEY_HEADER_NAME: str = "X-API-Key"

    # --- Rate limiting ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- Логирование ---
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False  # True для JSON-логов (ELK, Loki, облачные логи).

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def resolve_secret_files(self) -> "Settings":
        """Подставляет секреты из файлов, если заданы переменные *_FILE (Docker secrets)."""
        file_suffix = "_FILE"
        for name in ("BOT_TOKEN", "API_KEY", "BINANCE_API_SECRET"):
            file_env = os.environ.get(f"{name}{file_suffix}")
            if not file_env or not Path(file_env).is_file():
                continue
            value = _read_secret_from_file(file_env)
            if not value:
                continue
            if name == "BOT_TOKEN":
                object.__setattr__(self, "BOT_TOKEN", SecretStr(value))
            elif name == "API_KEY":
                object.__setattr__(self, "API_KEY", SecretStr(value))
            elif name == "BINANCE_API_SECRET":
                object.__setattr__(self, "BINANCE_API_SECRET", SecretStr(value))
        return self


settings = Settings()

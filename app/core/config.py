from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import List


class Settings(BaseSettings):
    # --- Бот ---
    BOT_TOKEN: SecretStr
    ADMIN_ID: int

    # --- Биржи ---
    # По умолчанию None, чтобы проект запустился без ключей
    BINANCE_API_KEY: str | None = None
    BINANCE_API_SECRET: SecretStr | None = None

    # --- Базы данных ---
    # Для Ubuntu Server по умолчанию используем локальный Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Настройки API и WebApp ---
    PROJECT_NAME: str = "ARKANA PULSE"
    API_V1_STR: str = "/api/v1"
    WEBAPP_URL: str = "http://localhost:8000"

    # --- CORS ---
    # Список доменов, которым разрешён доступ к API.
    # По умолчанию ["*"] для локальной разработки.
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # --- API‑ключ ---
    # Если API_KEY не задан, проверка ключа отключена (удобно для локальной разработки).
    API_KEY: SecretStr | None = None
    API_KEY_HEADER_NAME: str = "X-API-Key"

    # --- Ограничение частоты запросов (rate limiting) ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- Логирование ---
    LOG_LEVEL: str = "INFO"

    # --- Настройка загрузки ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Игнорировать лишние переменные в .env
    )


# Инициализируем один раз для всего проекта
settings = Settings()
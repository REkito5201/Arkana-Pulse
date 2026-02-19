from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field

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

    # --- Этот URL понадобится, когда мы запустим фронтенд ---
    WEBAPP_URL: str = "http://localhost:8000"

    # --- Настройка загрузки ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Игнорировать лишние переменные в .env
    )

# Инициализируем один раз для всего проекта
settings = Settings()
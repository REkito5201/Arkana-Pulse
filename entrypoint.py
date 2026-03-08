"""
Точка входа веб-API. Подключение роутеров, CORS, метрики, логирование.
"""
from __future__ import annotations

import json
import logging
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import router
from app.core.config import settings
from app.core.metrics import (
    PrometheusMiddleware,
    metrics_content,
    metrics_content_type,
)


class JsonLogFormatter(logging.Formatter):
    """Форматтер логов в JSON для сбора в ELK/Loki/облачные системы."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def _setup_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    if settings.LOG_JSON:
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[handler])
    # Уменьшаем шум от сторонних логгеров
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("arkana.entrypoint")

app = FastAPI(title=settings.PROJECT_NAME)

origins = settings.BACKEND_CORS_ORIGINS
allow_credentials = not (origins == ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMiddleware)

app.include_router(router, prefix=settings.API_V1_STR)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")


@app.get("/metrics")
async def metrics():
    """Метрики Prometheus. В production ограничьте доступ (nginx/firewall)."""
    return Response(
        content=metrics_content(),
        media_type=metrics_content_type(),
    )


if __name__ == "__main__":
    logger.info("🚀 Запуск %s...", settings.PROJECT_NAME)
    uvicorn.run(
        "entrypoint:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import router
from app.core.config import settings


logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("arkana.entrypoint")

app = FastAPI(title=settings.PROJECT_NAME)

origins = settings.BACKEND_CORS_ORIGINS
# Если явно указан список доменов, разрешаем креды; при '*' — отключаем.
allow_credentials = not (origins == ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем наши маршруты с префиксом
app.include_router(router, prefix=settings.API_V1_STR)

# Монтируем папку static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Главная страница, которая отдаёт наш HTML
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# Эта часть запускает сервер
if __name__ == "__main__":
    logger.info("🚀 Запуск %s...", settings.PROJECT_NAME)
    uvicorn.run(
        "entrypoint:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
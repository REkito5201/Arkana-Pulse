import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router
from app.core.config import settings
import os

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене лучше сменить на конкретный адрес
    allow_credentials=True,
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
    print(f"🚀 Запуск {settings.PROJECT_NAME}...")
    uvicorn.run(
        "entrypoint:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
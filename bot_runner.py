import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.core.config import settings


async def main():
    logging.basicConfig(level=logging.INFO)
    if not settings.BOT_TOKEN:
        raise ValueError("BOT_TOKEN или BOT_TOKEN_FILE обязателен для запуска бота")
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    dp = Dispatcher()

    # Подключаем обработчики (команды)
    dp.include_router(router)

    print("🤖 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
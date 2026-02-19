import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.core.config import settings
from app.bot.handlers import router

async def main():
    # Включаем логирование, чтобы видеть, если бот упадёт
    logging.basicConfig(level=logging.INFO)

    # Инициализируем бота и диспетчер
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    dp = Dispatcher()

    # Подключаем обработчики (команды)
    dp.include_router(router)

    print("🤖 Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
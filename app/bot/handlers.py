from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from app.engine.collectors import ExchangeCollector
from app.engine.scanner import MarketScanner

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    webapp_url = "https://womanish-transmeridionally-odessa.ngrok-free.dev/"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть WebApp 📈", web_app=WebAppInfo(url=webapp_url))]
    ])

    await message.answer(
        "👋 Привет! У нас появился WebApp. Нажми кнопку ниже:",
        reply_markup=markup
    )

@router.message(Command("check"))
async def cmd_check(message: types.Message):
    # Достаём тикер из сообщения (например, "BTCUSDT" из "/check BTCUSDT")
    args = message.text.split()
    symbol = args[1].upper() if len(args) > 1 else "BTCUSDT"

    msg = await message.answer(f"🔄 Анализирую {symbol}...")

    # Наша цепочка:
    collector = ExchangeCollector()
    scanner = MarketScanner()

    raw_data = await collector.fetch_klines(symbol=symbol)

    if not raw_data:
        await msg.edit_text("❌ Ошибка: Не удалось получить данные с Binance.")
        return
    
    df = scanner.analyze_assets(raw_data)
    res = scanner.get_signal(df)

    # Формируем красивый ответ
    text = (
        f"📊 *Сигнал для {symbol}*\n\n"
        f"💰 Цена: `{res['price']}`\n"
        f"📈 RSI: `{res['rsi']}`\n"
        f"🚦 Вердикт: *{res['signal']}*"
    )

    await msg.edit_text(text, parse_mode="Markdown")
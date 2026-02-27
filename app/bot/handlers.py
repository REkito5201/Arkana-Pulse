from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.engine.collectors import ExchangeCollector
from app.engine.fear_greed import FearGreedService
from app.engine.scanner import MarketScanner

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    webapp_url = "https://womanish-transmeridionally-odessa.ngrok-free.dev/"

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть WebApp 📈", web_app=WebAppInfo(url=webapp_url)
                )
            ]
        ]
    )

    await message.answer(
        "👋 Привет! У нас появился WebApp. Нажми кнопку ниже:",
        reply_markup=markup,
    )


@router.message(Command("check"))
async def cmd_check(message: types.Message) -> None:
    # Достаём тикер из сообщения (например, "BTCUSDT" из "/check BTCUSDT")
    args = message.text.split()
    symbol = args[1].upper() if len(args) > 1 else "BTCUSDT"

    msg = await message.answer(f"🔄 Анализирую {symbol}...")

    collector = ExchangeCollector()
    scanner = MarketScanner()

    raw_data = await collector.fetch_klines(symbol=symbol)
    if not raw_data:
        await msg.edit_text("❌ Ошибка: Не удалось получить данные с Binance.")
        return

    df = scanner.analyze_assets(raw_data)
    res = scanner.get_signal(df)

    text = (
        f"📊 *Сигнал для {symbol}*\n\n"
        f"💰 Цена: `{res['price']}`\n"
        f"📈 RSI: `{res['rsi']}`\n"
        f"🚦 Вердикт: *{res['signal']}*"
    )

    await msg.edit_text(text, parse_mode="Markdown")


@router.message(Command("fear_greed"))
async def cmd_fear_greed(message: types.Message) -> None:
    """Текущий индекс страха и жадности."""
    data = await FearGreedService.get_latest()
    if not data:
        await message.answer(
            "⚠️ Сейчас не удалось получить индекс страха и жадности. Попробуй позже."
        )
        return

    value = data["value"]
    classification = data["classification"]

    text = (
        "🧠 *Fear & Greed Index*\n\n"
        f"Текущее значение: *{value}* / 100\n"
        f"Классификация: *{classification}*"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("help_indicators"))
async def cmd_help_indicators(message: types.Message) -> None:
    """Краткие определения основных индикаторов."""
    text = (
        "📚 *Индикаторы, которые использует Arkana Pulse:*\n\n"
        "• *RSI (Relative Strength Index)* — показывает, перекуплен или перепродан рынок. "
        "Значения выше 70 часто означают перегрев, ниже 30 — перепроданность.\n\n"
        "• *Bollinger Bands* — две полосы вокруг средней цены. "
        "Помогают видеть периоды высокой волатильности и экстремальные отклонения цены.\n\n"
        "• *MACD* — разница между двумя EMA и её сглаживание. "
        "Гистограмма и линии помогают оценить силу тренда и возможный разворот.\n\n"
        "• *Ichimoku Cloud* — облако тренда. Линии Tenkan/Kijun и облако Span A/B "
        "показывают зоны поддержки/сопротивления и баланс цены.\n\n"
        "• *Fear & Greed Index* — агрегированный индекс настроений рынка от 0 (страх) "
        "до 100 (жадность). Экстремальные значения часто совпадают с разворотами."
    )

    await message.answer(text, parse_mode="Markdown")
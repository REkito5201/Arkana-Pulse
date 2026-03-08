# Обработчики команд Telegram-бота. Используют локализацию (i18n) и антиспам (reply_or_edit).
# WEBAPP_URL берётся из настроек — не хардкодим URL в коде (безопасность и смена окружения).

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot.anti_spam import reply_or_edit
from app.bot.i18n import get_user_lang, set_user_lang, t
from app.core.config import settings
from app.engine.collectors import ExchangeCollector
from app.engine.fear_greed import FearGreedService
from app.engine.scanner import MarketScanner

router = Router()

# Префикс callback_data для кнопок смены языка. Ограничиваем длину (лимит Telegram 64 байта).
LANG_CALLBACK_PREFIX = "lang:"


@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    # Язык: из Redis или из профиля Telegram (language_code), иначе en.
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    # URL WebApp из конфига: один источник правды, без секретов в коде.
    webapp_url = settings.WEBAPP_URL.strip().rstrip("/")
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("cmd_start.webapp_btn", lang),
                    web_app=WebAppInfo(url=webapp_url),
                )
            ]
        ]
    )
    # reply_or_edit: не плодим сообщения, обновляем последнее.
    await reply_or_edit(
        message,
        t("cmd_start.greeting", lang),
        reply_markup=markup,
    )


@router.message(Command("check"))
async def cmd_check(message: types.Message) -> None:
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    args = message.text.split()
    symbol = args[1].upper() if len(args) > 1 else "BTCUSDT"

    # Сначала показываем "Анализирую..."; то же сообщение потом заменим на результат (антиспам).
    await reply_or_edit(message, t("cmd_check.analyzing", lang, symbol=symbol))

    collector = ExchangeCollector()
    scanner = MarketScanner()
    raw_data = await collector.fetch_klines(symbol=symbol)

    if not raw_data:
        await reply_or_edit(message, t("cmd_check.error_no_data", lang))
        return

    df = scanner.analyze_assets(raw_data)
    res = scanner.get_signal(df)

    text = (
        t("cmd_check.signal_title", lang, symbol=symbol)
        + t("cmd_check.price", lang, value=res["price"])
        + t("cmd_check.rsi", lang, value=res["rsi"])
        + t("cmd_check.verdict", lang, value=res["signal"])
    )
    await reply_or_edit(message, text)


@router.message(Command("fear_greed"))
async def cmd_fear_greed(message: types.Message) -> None:
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    data = await FearGreedService.get_latest()
    if not data:
        await reply_or_edit(message, t("cmd_fear_greed.error", lang))
        return

    value = data["value"]
    classification = data["classification"]
    text = (
        t("cmd_fear_greed.title", lang)
        + t("cmd_fear_greed.value", lang, value=value)
        + t("cmd_fear_greed.classification", lang, value=classification)
    )
    await reply_or_edit(message, text)


@router.message(Command("help_indicators"))
async def cmd_help_indicators(message: types.Message) -> None:
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    text = (
        t("cmd_help_indicators.title", lang)
        + t("cmd_help_indicators.rsi", lang)
        + t("cmd_help_indicators.bb", lang)
        + t("cmd_help_indicators.macd", lang)
        + t("cmd_help_indicators.ichimoku", lang)
        + t("cmd_help_indicators.fear_greed", lang)
    )
    await reply_or_edit(message, text)


@router.message(Command("lang"))
async def cmd_lang(message: types.Message) -> None:
    """Показать текущий язык и кнопки выбора ru/en."""
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    display_name = "Русский" if lang == "ru" else "English"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("cmd_lang.btn_ru", lang),
                    callback_data=LANG_CALLBACK_PREFIX + "ru",
                ),
                InlineKeyboardButton(
                    text=t("cmd_lang.btn_en", lang),
                    callback_data=LANG_CALLBACK_PREFIX + "en",
                ),
            ]
        ]
    )
    await reply_or_edit(
        message,
        t("cmd_lang.current", lang, lang=display_name),
        reply_markup=markup,
    )


@router.callback_query(lambda c: c.data and c.data.startswith(LANG_CALLBACK_PREFIX))
async def callback_lang(callback: CallbackQuery) -> None:
    """Обработка нажатия кнопки языка: сохраняем в Redis и обновляем сообщение."""
    if not callback.data or not callback.message:
        return
    lang_code = callback.data[len(LANG_CALLBACK_PREFIX) :].lower()
    if lang_code not in ("ru", "en"):
        await callback.answer()
        return
    await set_user_lang(callback.message.chat.id, lang_code)
    feedback = t("cmd_lang.saved_ru", lang_code) if lang_code == "ru" else t("cmd_lang.saved_en", lang_code)
    await callback.message.edit_text(feedback, parse_mode="Markdown")
    await callback.answer()

# Обработчики команд Telegram-бота. Используют локализацию (i18n) и антиспам (reply_or_edit).
# WEBAPP_URL берётся из настроек — не хардкодим URL в коде (безопасность и смена окружения).

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot.anti_spam import delete_user_message_safely, reply_or_edit
from app.bot.i18n import get_user_lang, set_user_lang, t
from app.core.config import settings
from app.engine.collectors import ExchangeCollector
from app.engine.fear_greed import FearGreedService
from app.engine.scanner import MarketScanner

router = Router()

# Префиксы callback_data. Ограничиваем длину (лимит Telegram 64 байта).
LANG_CALLBACK_PREFIX = "lang:"
LEGEND_CALLBACK_PREFIX = "legend:"

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
    await reply_or_edit(message, t("cmd_start.greeting", lang), reply_markup=markup)
    await delete_user_message_safely(message)


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
    await delete_user_message_safely(message)


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
    await delete_user_message_safely(message)


@router.message(Command("legend"))
async def cmd_legend(message: types.Message) -> None:
    """Меню с определениями индикаторов (легенда)."""
    lang = await get_user_lang(
        message.chat.id,
        message.from_user.language_code if message.from_user else None,
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("legend.btn_rsi", lang),
                    callback_data=LEGEND_CALLBACK_PREFIX + "rsi",
                ),
                InlineKeyboardButton(
                    text=t("legend.btn_bb", lang),
                    callback_data=LEGEND_CALLBACK_PREFIX + "bb",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("legend.btn_macd", lang),
                    callback_data=LEGEND_CALLBACK_PREFIX + "macd",
                ),
                InlineKeyboardButton(
                    text=t("legend.btn_ichimoku", lang),
                    callback_data=LEGEND_CALLBACK_PREFIX + "ichimoku",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("legend.btn_fear_greed", lang),
                    callback_data=LEGEND_CALLBACK_PREFIX + "fear_greed",
                ),
            ],
        ]
    )
    await reply_or_edit(
        message,
        t("legend.menu_title", lang),
        reply_markup=markup,
    )
    await delete_user_message_safely(message)


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
        t("cmd_lang.current", lang, current=display_name),
        reply_markup=markup,
    )
    await delete_user_message_safely(message)


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


@router.callback_query(lambda c: c.data and c.data.startswith(LEGEND_CALLBACK_PREFIX))
async def callback_legend(callback: CallbackQuery) -> None:
    """Отправка определения индикатора из легенды по нажатию на кнопку."""
    if not callback.data or not callback.message:
        return

    key = callback.data[len(LEGEND_CALLBACK_PREFIX) :].lower()
    if key not in ("rsi", "bb", "macd", "ichimoku", "fear_greed"):
        await callback.answer()
        return

    lang = await get_user_lang(
        callback.message.chat.id,
        callback.from_user.language_code if callback.from_user else None,
    )
    text_key = f"legend.{key}"
    await callback.message.edit_text(t(text_key, lang), parse_mode="Markdown")
    await callback.answer()

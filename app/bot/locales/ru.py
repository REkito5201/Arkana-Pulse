# Русские строки бота. Ключ — идентификатор (используется в коде), значение — текст для пользователя.
# Best practice: не хардкодить строки в handlers, держать их здесь для удобной правки и аудита.

RU = {
    # /start
    "cmd_start.greeting": "👋 Привет! У нас появился WebApp. Нажми кнопку ниже:",
    "cmd_start.webapp_btn": "Открыть WebApp 📈",
    # /check
    "cmd_check.analyzing": "🔄 Анализирую {symbol}...",
    "cmd_check.error_no_data": "❌ Ошибка: Не удалось получить данные с Binance.",
    "cmd_check.signal_title": "📊 *Сигнал для {symbol}*\n\n",
    "cmd_check.price": "💰 Цена: `{value}`\n",
    "cmd_check.rsi": "📈 RSI: `{value}`\n",
    "cmd_check.verdict": "🚦 Вердикт: *{value}*",
    # /fear_greed
    "cmd_fear_greed.error": "⚠️ Сейчас не удалось получить индекс страха и жадности. Попробуй позже.",
    "cmd_fear_greed.title": "🧠 *Fear & Greed Index*\n\n",
    "cmd_fear_greed.value": "Текущее значение: *{value}* / 100\n",
    "cmd_fear_greed.classification": "Классификация: *{value}*",
    # /help_indicators
    "cmd_help_indicators.title": "📚 *Индикаторы, которые использует Arkana Pulse:*\n\n",
    "cmd_help_indicators.rsi": "• *RSI (Relative Strength Index)* — показывает, перекуплен или перепродан рынок. "
    "Значения выше 70 часто означают перегрев, ниже 30 — перепроданность.\n\n",
    "cmd_help_indicators.bb": "• *Bollinger Bands* — две полосы вокруг средней цены. "
    "Помогают видеть периоды высокой волатильности и экстремальные отклонения цены.\n\n",
    "cmd_help_indicators.macd": "• *MACD* — разница между двумя EMA и её сглаживание. "
    "Гистограмма и линии помогают оценить силу тренда и возможный разворот.\n\n",
    "cmd_help_indicators.ichimoku": "• *Ichimoku Cloud* — облако тренда. Линии Tenkan/Kijun и облако Span A/B "
    "показывают зоны поддержки/сопротивления и баланс цены.\n\n",
    "cmd_help_indicators.fear_greed": "• *Fear & Greed Index* — агрегированный индекс настроений рынка от 0 (страх) "
    "до 100 (жадность). Экстремальные значения часто совпадают с разворотами.",
    # /lang
    "cmd_lang.current": "🌐 Язык: *{lang}*. Выбери другой:",
    "cmd_lang.saved_ru": "✅ Язык изменён на русский.",
    "cmd_lang.saved_en": "✅ Language set to English.",
    "cmd_lang.btn_ru": "🇷🇺 Русский",
    "cmd_lang.btn_en": "🇬🇧 English",
}

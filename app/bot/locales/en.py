# English bot strings. Key = identifier used in code, value = user-facing text.
# Kept in sync with ru.py keys so t(key, "en") / t(key, "ru") always have a value.

EN = {
    "cmd_start.greeting": "👋 Hi! We have a WebApp. Tap the button below:",
    "cmd_start.webapp_btn": "Open WebApp 📈",
    "cmd_check.analyzing": "🔄 Analyzing {symbol}...",
    "cmd_check.error_no_data": "❌ Error: Could not fetch data from Binance.",
    "cmd_check.signal_title": "📊 *Signal for {symbol}*\n\n",
    "cmd_check.price": "💰 Price: `{value}`\n",
    "cmd_check.rsi": "📈 RSI: `{value}`\n",
    "cmd_check.verdict": "🚦 Verdict: *{value}*",
    "cmd_fear_greed.error": "⚠️ Could not get Fear & Greed index right now. Try again later.",
    "cmd_fear_greed.title": "🧠 *Fear & Greed Index*\n\n",
    "cmd_fear_greed.value": "Current value: *{value}* / 100\n",
    "cmd_fear_greed.classification": "Classification: *{value}*",
    "cmd_help_indicators.title": "📚 *Indicators used by Arkana Pulse:*\n\n",
    "cmd_help_indicators.rsi": "• *RSI (Relative Strength Index)* — shows if the market is overbought or oversold. "
    "Values above 70 often mean overheated, below 30 — oversold.\n\n",
    "cmd_help_indicators.bb": "• *Bollinger Bands* — two bands around the average price. "
    "Help see high volatility periods and extreme price deviations.\n\n",
    "cmd_help_indicators.macd": "• *MACD* — difference between two EMAs and its smoothing. "
    "Histogram and lines help assess trend strength and possible reversal.\n\n",
    "cmd_help_indicators.ichimoku": "• *Ichimoku Cloud* — trend cloud. Tenkan/Kijun lines and Span A/B cloud "
    "show support/resistance zones and price balance.\n\n",
    "cmd_help_indicators.fear_greed": "• *Fear & Greed Index* — aggregated market sentiment from 0 (fear) "
    "to 100 (greed). Extreme values often align with reversals.",
    # /legend
    "legend.menu_title": "📚 Choose an indicator to see a short definition:",
    "legend.btn_rsi": "RSI",
    "legend.btn_bb": "Bollinger Bands",
    "legend.btn_macd": "MACD",
    "legend.btn_ichimoku": "Ichimoku",
    "legend.btn_fear_greed": "Fear & Greed Index",
    "legend.btn_back": "⬅️ Back",
    "legend.rsi": "📊 *RSI (Relative Strength Index)*\n\n"
    "Oscillator from 0 to 100. Values above 70 often mean overbought market, below 30 — oversold.",
    "legend.bb": "📊 *Bollinger Bands*\n\n"
    "Bands around the average price. Upper and lower bands help see statistically high and low price values.",
    "legend.macd": "📊 *MACD*\n\n"
    "Difference between two exponential moving averages and its smoothing. Lines and histogram show trend strength "
    "and possible reversals.",
    "legend.ichimoku": "📊 *Ichimoku Cloud*\n\n"
    "Complex trend indicator. Span A/B cloud defines support/resistance zones, Tenkan/Kijun lines show price balance.",
    "legend.fear_greed": "📊 *Fear & Greed Index*\n\n"
    "Aggregated market sentiment from 0 (fear) to 100 (greed). Extreme values often coincide with market reversals.",
    "cmd_lang.current": "🌐 Language: *{current}*. Choose another:",
    "cmd_lang.saved_ru": "✅ Язык изменён на русский.",
    "cmd_lang.saved_en": "✅ Language set to English.",
    "cmd_lang.btn_ru": "🇷🇺 Русский",
    "cmd_lang.btn_en": "🇬🇧 English",
}

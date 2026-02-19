import polars as pl
import pandas_ta as ta

class MarketScanner:
    def __init__(self):
        # В будущем здесь будет подключение к Redis
        pass
    
    def analyze_assets(self, raw_data: list) -> pl.DataFrame:
        """
        Превращает "сырые" свечи в аналитическую таблицу.
        raw_data: список списков от Биржи [[time, open, high, low, close, vol], ...]
        """
        if not raw_data:
            return pl.DataFrame()

        # 1. Создаём DataFrame (Таблицу)
        df = pl.DataFrame(
            raw_data,
            schema=["timestamp", "open", "high", "low", "close", "volume"],
            orient="row"
        )

        # 2. Приводим типы к числам (Float64)
        df = df.with_columns([
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64)
        ])

        # 3. Считаем RSI (Индикатор относительной силы)
        # pandas_ta считает RSI, а Polars мгновенно вставляет его в таблицу
        rsi_series = ta.rsi(df["close"].to_pandas(), length=14)

        df = df.with_columns([
            pl.from_pandas(rsi_series).alias("rsi")
        ])

        return df
    def get_signal(self, df: pl.DataFrame) -> dict:
        """Берёт последнюю строку таблицы и даёт вердикт"""
        if df.is_empty():
            return {"error": "Нет данных"}
        
        last_row = df.tail(1).to_dicts()[0]
        rsi = last_row.get("rsi")

        # Простая логика сигналов
        result = "NEUTRAL"
        if rsi and rsi > 70: result = "OVERBOUGHT (SELL)"
        if rsi and rsi < 30: result = "OVERSOLD (BUY)"

        return {
            "price": last_row["close"],
            "rsi": round(rsi, 2) if rsi else None,
            "signal": result
        }
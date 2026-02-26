import polars as pl
import pandas_ta as ta
from typing import Optional

class MarketScanner:
    def __init__(self):
        # Параметры индикаторов вынесены в константы для гибкости
        self.bb_period = 20
        self.bb_std = 2
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def analyze_assets(self, raw_data: list) -> pl.DataFrame:
        """
        Превращает "сырые" свечи в аналитическую таблицу с BB и MACD.
        """
        if not raw_data:
            return pl.DataFrame()

        # 1. Создаём DataFrame и приводим типы
        df = pl.DataFrame(
            raw_data,
            schema=["timestamp", "open", "high", "low", "close", "volume"],
            orient="row"
        ).with_columns([
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Float64)
        ])

        # 2. RSI (оставляем через pandas_ta для совместимости)
        rsi_series = ta.rsi(df["close"].to_pandas(), length=14)
        df = df.with_columns([pl.from_pandas(rsi_series).alias("rsi")])

        # 3. Bollinger Bands (Нативный Polars)
        # Считаем среднее и стандартное отклонение за период
        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=self.bb_period).alias("bb_mid"),
            pl.col("close").rolling_std(window_size=self.bb_period).alias("bb_std_dev")
        ])
        
        # Формируем верхнюю и нижнюю границы
        df = df.with_columns([
            (pl.col("bb_mid") + (pl.col("bb_std_dev") * self.bb_std)).alias("bb_upper"),
            (pl.col("bb_mid") - (pl.col("bb_std_dev") * self.bb_std)).alias("bb_lower")
        ])

        # 4. MACD (Нативный Polars через EWM)
        # Считаем две экспоненциальные скользящие средние (EMA)
        ema_fast = pl.col("close").ewm_mean(span=self.macd_fast, adjust=False)
        ema_slow = pl.col("close").ewm_mean(span=self.macd_slow, adjust=False)
        
        df = df.with_columns([
            (ema_fast - ema_slow).alias("macd_line")
        ])
        
        # Сигнальная линия и гистограмма
        df = df.with_columns([
            pl.col("macd_line").ewm_mean(span=self.macd_signal, adjust=False).alias("macd_signal"),
        ]).with_columns([
            (pl.col("macd_line") - pl.col("macd_signal")).alias("macd_hist")
        ])

        return df

    def get_signal(self, df: pl.DataFrame) -> dict:
        """Расширенный вердикт на основе нескольких индикаторов."""
        if df.is_empty():
            return {"error": "Нет данных"}
        
        last = df.tail(1).to_dicts()[0]
        rsi = last.get("rsi")
        close = last.get("close")
        
        # Базовая логика: RSI + Bollinger
        signal = "NEUTRAL"
        if rsi:
            if rsi > 70 or close > last.get("bb_upper", 0):
                signal = "OVERBOUGHT (SELL)"
            elif rsi < 30 or close < last.get("bb_lower", 0):
                signal = "OVERSOLD (BUY)"

        return {
            "price": close,
            "rsi": round(rsi, 2) if rsi else None,
            "bb_upper": round(last.get("bb_upper"), 2) if last.get("bb_upper") else None,
            "macd_hist": round(last.get("macd_hist"), 4) if last.get("macd_hist") else None,
            "signal": signal
        }
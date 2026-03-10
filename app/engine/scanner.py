import logging

import polars as pl
import pandas_ta as ta

logger = logging.getLogger(__name__)


class MarketScanner:
    def __init__(self) -> None:
        # Параметры индикаторов вынесены в константы для гибкости
        self.bb_period = 20
        self.bb_std = 2
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def analyze_assets(self, raw_data: list) -> pl.DataFrame:
        """
        Превращает "сырые" свечи в аналитическую таблицу с RSI, Bollinger Bands,
        MACD и Ichimoku.
        """
        if not raw_data:
            return pl.DataFrame()

        # 1. Создаём DataFrame и приводим типы
        df = pl.DataFrame(
            raw_data,
            schema=["timestamp", "open", "high", "low", "close", "volume"],
            orient="row",
        ).with_columns(
            [
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Float64),
            ]
        )

        # 2. RSI (оставляем через pandas_ta для совместимости)
        rsi_series = ta.rsi(df["close"].to_pandas(), length=14)
        df = df.with_columns([pl.from_pandas(rsi_series).alias("rsi")])

        # 3. Bollinger Bands (нативный Polars)
        df = df.with_columns(
            [
                pl.col("close")
                .rolling_mean(window_size=self.bb_period)
                .alias("bb_mid"),
                pl.col("close")
                .rolling_std(window_size=self.bb_period)
                .alias("bb_std_dev"),
            ]
        )

        df = df.with_columns(
            [
                (pl.col("bb_mid") + (pl.col("bb_std_dev") * self.bb_std)).alias(
                    "bb_upper"
                ),
                (pl.col("bb_mid") - (pl.col("bb_std_dev") * self.bb_std)).alias(
                    "bb_lower"
                ),
            ]
        )

        # 4. MACD (нативный Polars через EWM)
        ema_fast = pl.col("close").ewm_mean(span=self.macd_fast, adjust=False)
        ema_slow = pl.col("close").ewm_mean(span=self.macd_slow, adjust=False)

        df = df.with_columns([(ema_fast - ema_slow).alias("macd_line")])

        df = df.with_columns(
            [
                pl.col("macd_line")
                .ewm_mean(span=self.macd_signal, adjust=False)
                .alias("macd_signal"),
            ]
        ).with_columns(
            [(pl.col("macd_line") - pl.col("macd_signal")).alias("macd_hist")]
        )

        # 5. Ichimoku (через pandas_ta): возвращает (ichimokudf, spandf)
        high_pd = df["high"].to_pandas()
        low_pd = df["low"].to_pandas()
        close_pd = df["close"].to_pandas()
        tenkan, kijun, senkou = 9, 26, 52

        try:
            result = ta.ichimoku(
                high=high_pd,
                low=low_pd,
                close=close_pd,
                tenkan=tenkan,
                kijun=kijun,
                senkou=senkou,
            )
            if result is None or result[0] is None:
                logger.warning("Ichimoku returned None (insufficient data?)")
                return df

            ichimokudf, _spandf = result
            # Колонки: ISA_9, ISB_26, ITS_9, IKS_26 (и опционально Chikou)
            col_conv = f"ITS_{tenkan}"
            col_base = f"IKS_{kijun}"
            col_span_a = f"ISA_{tenkan}"
            col_span_b = f"ISB_{kijun}"
            if not all(c in ichimokudf.columns for c in (col_conv, col_base, col_span_a, col_span_b)):
                logger.warning("Ichimoku DataFrame missing expected columns: %s", list(ichimokudf.columns))
                return df

            df = df.with_columns(
                [
                    pl.from_pandas(ichimokudf[col_conv]).alias("ichi_conversion"),
                    pl.from_pandas(ichimokudf[col_base]).alias("ichi_base"),
                    pl.from_pandas(ichimokudf[col_span_a]).alias("ichi_span_a"),
                    pl.from_pandas(ichimokudf[col_span_b]).alias("ichi_span_b"),
                ]
            )
        except Exception as e:
            logger.exception("Ichimoku calculation failed: %s", e)

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
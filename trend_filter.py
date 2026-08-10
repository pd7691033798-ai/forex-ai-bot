import pandas as pd
import numpy as np
import logging

class TrendFilterEngine:
    def __init__(self, ema_period: int = 200):
        self.ema_period = ema_period

    def calculate_ema(self, prices: list, period: int) -> float:
        if not prices or len(prices) < period:
            return None
        
        series = pd.Series(prices)
        ema_series = series.ewm(span=period, adjust=False).mean()
        return float(ema_series.iloc[-1])

    def evaluate_multi_timeframe_alignment(self, data_1h: list, data_15m: list, data_5m: list) -> dict:
        if not data_1h or not data_15m or not data_5m:
            return {"allowed": False, "reason": "Insufficient Data Received", "direction": "NONE"}

        if len(data_1h) < self.ema_period or len(data_15m) < 50 or len(data_5m) < 20:
            return {"allowed": False, "reason": "Data Length Too Short for EMA Calculation", "direction": "NONE"}

        ema_1h = self.calculate_ema(data_1h, self.ema_period)
        ema_15m = self.calculate_ema(data_15m, 50)
        ema_5m = self.calculate_ema(data_5m, 20)

        if ema_1h is None or ema_15m is None or ema_5m is None:
            return {"allowed": False, "reason": "EMA Calculation Failed", "direction": "NONE"}

        price_1h = data_1h[-1]
        price_15m = data_15m[-1]
        price_5m = data_5m[-1]

        if price_1h > ema_1h and price_15m > ema_15m and price_5m > ema_5m:
            return {"allowed": True, "reason": "Bullish Trend Confluence Passed", "direction": "BUY"}

        elif price_1h < ema_1h and price_15m < ema_15m and price_5m < ema_5m:
            return {"allowed": True, "reason": "Bearish Trend Confluence Passed", "direction": "SELL"}

        return {"allowed": False, "reason": "Trend Alignment Failed Across Timeframes", "direction": "NONE"}

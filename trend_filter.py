import pandas as pd
import numpy as np
import logging

class TrendFilterEngine:
    def __init__(self, ema_period: int = 200):
        self.ema_period = ema_period

    def calculate_ema(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0.0
        return float(pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1])

    def evaluate_multi_timeframe_alignment(self, data_1h: list, data_15m: list, data_5m: list) -> dict:
        if not data_1h or not data_15m or not data_5m:
            return {"allowed": False, "reason": "Insufficient Data", "direction": "NONE"}

        ema_1h = self.calculate_ema(data_1h, self.ema_period)
        ema_15m = self.calculate_ema(data_15m, 50)
        ema_5m = self.calculate_ema(data_5m, 20)

        price_1h = data_1h[-1]
        price_15m = data_15m[-1]
        price_5m = data_5m[-1]

        # Check Bullish Confluence
        if price_1h > ema_1h and price_15m > ema_15m and price_5m > ema_5m:
            return {"allowed": True, "reason": "Bullish Trend Confluence Passed", "direction": "BUY"}

        # Check Bearish Confluence
        elif price_1h < ema_1h and price_15m < ema_15m and price_5m < ema_5m:
            return {"allowed": True, "reason": "Bearish Trend Confluence Passed", "direction": "SELL"}

        return {"allowed": False, "reason": "Trend Alignment Failed Across Timeframes", "direction": "NONE"}

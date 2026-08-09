import os
import json
import asyncio
import logging
import websockets
from typing import Dict, Any, List

# Phase 2 का Trend Filter Import करें
from trend_filter import TrendFilterEngine

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")


# ==============================================================================
# 🧠 PART 1: ADVANCED SYMBOL & MODE MANAGER
# ==============================================================================
class SymbolConfigManager:
    SYMBOLS_CATALOG = {
        "SYNTHETIC": {
            "VOLATILITY_100_1S": "1HZ100V",  # ⚡ 24/7 Live Ticks
            "VOLATILITY_100":    "R_100",
            "VOLATILITY_75":     "R_75",
        },
        "FOREX": {
            "EURUSD": "frxEURUSD",
            "GBPUSD": "frxGBPUSD",
            "GOLD":   "frxXAUUSD"
        }
    }

    def __init__(self, mode: str = "SYNTHETIC", symbol_key: str = "VOLATILITY_100_1S"):
        self.mode = os.getenv("TRADING_MODE", mode).upper()
        self.symbol_key = symbol_key.upper()
        self.active_symbol = self._resolve_symbol()

    def _resolve_symbol(self) -> str:
        if self.mode not in self.SYMBOLS_CATALOG:
            self.mode = "SYNTHETIC"

        category = self.SYMBOLS_CATALOG[self.mode]
        symbol = category.get(self.symbol_key, "1HZ100V")
        logging.info(f"🚀 Active Mode: [{self.mode}] | Target Symbol: [{symbol}]")
        return symbol


# ==============================================================================
# ⚡ PART 2: MULTI-TIMEFRAME WEBSOCKET SUBSCRIBER ENGINE
# ==============================================================================
class MarketDataSubscriber:
    GRANULARITIES = {"1H": 3600, "15M": 900, "5M": 300}

    def __init__(self, active_symbol: str, count: int = 250):
        self.active_symbol = active_symbol
        self.count = count

    def generate_subscription_payload(self, timeframe: str) -> Dict[str, Any]:
        granularity = self.GRANULARITIES.get(timeframe, 300)
        return {
            "ticks_history": self.active_symbol,
            "adjust_start_time": 1,
            "count": self.count,
            "end": "latest",
            "style": "candles",
            "granularity": granularity,
            "subscribe": 1,
            "passthrough": {"timeframe": timeframe}
        }

    async def subscribe_all_timeframes(self, ws):
        for tf in ["1H", "15M", "5M"]:
            payload = self.generate_subscription_payload(timeframe=tf)
            await ws.send(json.dumps(payload))
            logging.info(f"✅ Subscribed to [{self.active_symbol}] - Timeframe: {tf}")


# ==============================================================================
# 🎯 PART 3: WEBSOCKET EVENT LOOP & PHASE 2 SIGNAL PROCESSING
# ==============================================================================
# Global Memory Storage for Candle Prices
candles_data_store = {
    "1H": [],
    "15M": [],
    "5M": []
}

trend_engine = TrendFilterEngine(ema_period=200)


async def process_incoming_message(response_text: str):
    """
    Deriv से आने वाले हर लाइव डेटा रिस्पॉन्स को प्रोसेस और फ़िल्टर करता है
    """
    try:
        data = json.loads(response_text)
        
        # Check if response contains candle history
        if "candles" in data:
            passthrough = data.get("echo_req", {}).get("passthrough", {})
            tf = passthrough.get("timeframe")

            if tf in candles_data_store:
                # Extract close prices from candle array
                close_prices = [float(c["close"]) for c in data["candles"]]
                candles_data_store[tf] = close_prices
                logging.info(f"📈 Received {len(close_prices)} candles for Timeframe: {tf}")

                # जब तीनों (1H, 15M, 5M) का डेटा आ जाए, तब Trend Check करें
                if (len(candles_data_store["1H"]) >= 200 and 
                    len(candles_data_store["15M"]) >= 200 and 
                    len(candles_data_store["5M"]) >= 200):
                    
                    alignment = trend_engine.evaluate_multi_timeframe_alignment(
                        data_1h=candles_data_store["1H"],
                        data_15m=candles_data_store["15M"],
                        data_5m=candles_data_store["5M"]
                    )

                    if alignment["allowed"]:
                        logging.info(f"🎯 TRADE SIGNAL APPROVED | Direction: {alignment['direction']} | {alignment['reason']}")
                        # -------------------------------------------------------------
                        # HERE: आगे ऑर्डर प्लेस करने (Deriv Buy Order) का लॉजिक आएगा
                        # -------------------------------------------------------------
                    else:
                        logging.info(f"🚫 SIGNAL REJECTED: {alignment['reason']}")

    except Exception as e:
        logging.error(f"Error processing message: {e}")


async def main_loop():
    """
    WebSocket Main Connection Loop
    """
    # 1. Active Symbol Config (आज संडे है इसलिए 'SYNTHETIC' एक्टिव है)
    config = SymbolConfigManager(mode="SYNTHETIC", symbol_key="VOLATILITY_100_1S")
    subscriber = MarketDataSubscriber(active_symbol=config.active_symbol, count=250)

    app_id = os.getenv("DERIV_APP_ID", "1089") # Default App ID
    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={app_id}"

    async with websockets.connect(ws_url) as ws:
        logging.info("🔗 Connected to Deriv WebSocket Server")
        
        # Subscribe to 1H, 15M, 5M Timeframes
        await subscriber.subscribe_all_timeframes(ws)

        # Continuous Listening Loop
        async for msg in ws:
            await process_incoming_message(msg)


if __name__ == "__main__":
    asyncio.run(main_loop())


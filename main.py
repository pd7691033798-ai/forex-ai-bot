import os
import time
import json
import asyncio
import logging
import datetime
import requests
import websockets
import threading
import pandas as pd
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Tuple

from news_guard import EconomicNewsGuard

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# Global Engines
news_guard = EconomicNewsGuard()

# 1. Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089").strip()
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "").strip()

# Deriv Standard Symbol Names
SYMBOLS_TO_SCAN = [
    "R_10", "R_25", "R_50", "R_75", "R_100",  # Deriv Synthetic Volatility (24/7)
    "frxEURUSD", "frxGBPUSD"                   # Major Forex Pairs
]

# Health Check Server Handler for Render
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Smart Balance Master Engine Active")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"🌐 Health Check Server running on port {port}")
    server.serve_forever()

def send_telegram_message(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram Bot Token or Chat ID missing in Environment Variables.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

class RuleSet1CapitalGuardian:
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity = initial_balance
        self.daily_start_balance = initial_balance
        self.risk_per_trade_pct = 1.0 
        self.max_daily_loss_pct = 3.0
        self.active_positions_count = 0

    def update_balance(self, balance: float):
        self.current_balance = balance
        self.equity = balance

    def get_1pct_stake_amount(self):
        stake = self.current_balance * (self.risk_per_trade_pct / 100.0)
        return round(max(1.0, stake), 2)

    def check_safety_guards(self) -> Tuple[bool, str]:
        daily_loss = (self.daily_start_balance - self.equity) / self.daily_start_balance * 100.0
        if daily_loss >= self.max_daily_loss_pct:
            return False, f"🛡️ Rule 2: Daily Loss Limit Triggered ({daily_loss:.2f}%)"
        if self.active_positions_count >= 1:
            return False, "🛡️ Max Concurrent Trades Limit Reached (1 Active Max)"
        return True, "🟢 Clear"

guardian = RuleSet1CapitalGuardian()

# ==================== RELAXED STRATEGY ENGINE ====================

class OptimizedSignalEngine:
    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))

    def calculate_indicators_5m(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        df = df_5m.copy()
        df.columns = df.columns.str.lower()
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['rsi'] = self.calculate_rsi(df['close'], period=14)
        
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(14).mean()
        return df

    def get_1h_trend(self, df_1h: pd.DataFrame) -> str:
        df = df_1h.copy()
        df.columns = df.columns.str.lower()
        if len(df) < 50:
            return "NEUTRAL"
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()
        current_close = df['close'].iloc[-1]
        current_ema = ema_50.iloc[-1]
        
        if current_close > current_ema:
            return "UPTREND"
        elif current_close < current_ema:
            return "DOWNTREND"
        return "NEUTRAL"

    def evaluate_signals(self, df_1h: pd.DataFrame, df_5m: pd.DataFrame) -> Tuple[str, str]:
        # News Check
        is_news, news_reason = news_guard.is_high_impact_news_near()
        if is_news:
            return "HOLD", f"News Block: {news_reason}"

        if df_5m is None or len(df_5m) < 25:
            return "HOLD", "Insufficient 5M data"
        if df_1h is None or len(df_1h) < 50:
            return "HOLD", "Insufficient 1H data"

        df_5m = self.calculate_indicators_5m(df_5m)
        trend_1h = self.get_1h_trend(df_1h)
        
        curr = df_5m.iloc[-1]
        prev = df_5m.iloc[-2]

        if pd.isna(curr['atr']) or pd.isna(curr['rsi']):
            return "HOLD", "Indicators warming up (NaN)"

        # BUY / CALL Logic
        ema_bullish_cross = (prev['ema_9'] <= prev['ema_21']) and (curr['ema_9'] > curr['ema_21'])
        if trend_1h == "UPTREND" and ema_bullish_cross and (35 <= curr['rsi'] <= 65):
            return "CALL", "1H Uptrend + 5M EMA Cross + Balanced RSI"

        # SELL / PUT Logic
        ema_bearish_cross = (prev['ema_9'] >= prev['ema_21']) and (curr['ema_9'] < curr['ema_21'])
        if trend_1h == "DOWNTREND" and ema_bearish_cross and (35 <= curr['rsi'] <= 65):
            return "PUT", "1H Downtrend + 5M EMA Cross + Balanced RSI"

        return "HOLD", "No condition met"

signal_engine = OptimizedSignalEngine()

# Deriv API WebSocket Connection URL
ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

async def fetch_deriv_candle_df(symbol: str, granularity: int, count: int = 100, retries: int = 3) -> pd.DataFrame:
    for attempt in range(1, retries + 1):
        try:
            async with websockets.connect(
                ws_url,
                open_timeout=20,
                close_timeout=10,
                ping_interval=20,
                ping_timeout=20
            ) as ws:
                req = {
                    "ticks_history": symbol,
                    "adjust_start_time": 1,
                    "count": count,
                    "end": "latest",
                    "start": 1,
                    "style": "candles",
                    "granularity": granularity
                }
                await ws.send(json.dumps(req))
                
                start_time = time.time()
                while time.time() - start_time < 10:
                    resp = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(resp)

                    if "candles" in data:
                        df = pd.DataFrame(data["candles"])
                        for col in ['open', 'high', 'low', 'close', 'epoch']:
                            if col in df.columns:
                                df[col] = df[col].astype(float)
                        return df
                    elif "error" in data:
                        logging.warning(f"Deriv API Error on {symbol} ({granularity}s): {data['error'].get('message', 'Unknown Error')}")
                        return pd.DataFrame()
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(1.0 * attempt)
            else:
                logging.error(f"Live Data Fetch Error on {symbol} ({granularity}s): {e}")
    return pd.DataFrame()

async def execute_deriv_trade(symbol: str, contract_type: str, stake: float) -> bool:
    if not DERIV_API_TOKEN:
        logging.error("❌ Deriv API Token Missing in Environment Variables.")
        send_telegram_message("❌ *Deriv Trade Error*: `DERIV_API_TOKEN` environment variable me nahi mila.")
        return False

    try:
        async with websockets.connect(
            ws_url,
            open_timeout=20,
            close_timeout=10,
            ping_interval=20,
            ping_timeout=20
        ) as ws:
            # 1. Authorize Token
            auth_req = {"authorize": DERIV_API_TOKEN}
            await ws.send(json.dumps(auth_req))
            
            auth_resp = await asyncio.wait_for(ws.recv(), timeout=15)
            auth_data = json.loads(auth_resp)

            if "error" in auth_data:
                err_msg = auth_data["error"].get("message", "Authorization failed")
                logging.error(f"❌ Deriv Auth Error: {err_msg}")
                send_telegram_message(f"❌ *Deriv Auth Error*: {err_msg}\nPlease verify API Token permissions.")
                return False

            if "authorize" in auth_data:
                bal = float(auth_data["authorize"].get("balance", guardian.current_balance))
                guardian.update_balance(bal)

            # 2. Execute Trade Order
            buy_req = {
                "buy": 1,
                "price": stake,
                "parameters": {
                    "amount": stake,
                    "basis": "stake",
                    "contract_type": contract_type,
                    "currency": "USD",
                    "duration": 5,
                    "duration_unit": "m",
                    "symbol": symbol
                }
            }
            await ws.send(json.dumps(buy_req))
            buy_resp = await asyncio.wait_for(ws.recv(), timeout=15)
            buy_data = json.loads(buy_resp)

            if "error" in buy_data:
                err_msg = buy_data["error"].get("message", "Order Rejected")
                logging.error(f"❌ Trade Execution Error: {err_msg}")
                send_telegram_message(f"⚠️ *Trade Failed* on {symbol}: {err_msg}")
                return False

            contract_id = buy_data["buy"]["contract_id"]
            logging.info(f"✅ Trade Placed Successfully on {symbol}! Contract ID: {contract_id}")
            send_telegram_message(f"🚀 *TRADE EXECUTED*\n\n*Asset:* `{symbol}`\n*Type:* `{contract_type}`\n*Stake:* `${stake}`\n*Contract ID:* `{contract_id}`\n*Duration:* 5 Min")
            return True
    except Exception as e:
        logging.error(f"Trade Execution Exception: {e}")
        return False

async def manage_trade_duration(duration_seconds: int):
    """Background task to release position lock after duration without freezing scanner"""
    await asyncio.sleep(duration_seconds)
    guardian.active_positions_count = max(0, guardian.active_positions_count - 1)
    logging.info("🔓 Trade duration completed. Position lock released.")

async def market_scanning_loop():
    logging.info("🔎 Multi-Asset Scanner Active (5M EMA/RSI Strategy with 1H Trend)...")
    send_telegram_message("🚀 *Multi-Asset Engine Online*\nScanning Assets on 5M EMA & RSI Balanced Strategy!")

    while True:
        try:
            is_safe, safety_reason = guardian.check_safety_guards()
            if not is_safe:
                logging.warning(f"Safety Guard Active: {safety_reason}")
                await asyncio.sleep(15)
                continue

            for symbol in SYMBOLS_TO_SCAN:
                df_1h = await fetch_deriv_candle_df(symbol, 3600, 70)
                df_5m = await fetch_deriv_candle_df(symbol, 300, 50)

                if df_1h.empty or df_5m.empty:
                    await asyncio.sleep(0.3)
                    continue

                signal, reason = signal_engine.evaluate_signals(df_1h, df_5m)

                if signal in ["CALL", "PUT"]:
                    logging.info(f"🎯 Valid Trade Signal on {symbol}: {signal} | Reason: {reason}")
                    stake = guardian.get_1pct_stake_amount()
                    
                    guardian.active_positions_count += 1
                    success = await execute_deriv_trade(symbol, signal, stake)
                    
                    if success:
                        # Non-blocking async timer for 5 minutes
                        asyncio.create_task(manage_trade_duration(300))
                    else:
                        guardian.active_positions_count = max(0, guardian.active_positions_count - 1)

                await asyncio.sleep(0.3)

        except Exception as e:
            logging.error(f"Market Scanning Loop Error: {e}")
        
        await asyncio.sleep(5)

def main():
    # Start Health Check Server for Render
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

    logging.info("🚀 Starting Complete Multi-Asset Engine...")
    asyncio.run(market_scanning_loop())

if __name__ == "__main__":
    main()

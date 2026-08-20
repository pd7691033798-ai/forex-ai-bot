import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
import requests
import websockets

# ---------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s"
)

# ---------------------------------------------------------
# Environment Variables & Global Config
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "1089").strip()
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "").strip()

# Mode: "AUTO" (24/7 Execution) ya "COPILOT" (Manual Approval)
CURRENT_TRADING_MODE = os.getenv("TRADING_MODE", "COPILOT").upper()

SYMBOLS_TO_SCAN = [
    "R_10",
    "R_25",
    "R_50",
    "R_75",
    "R_100",  # Deriv Synthetic Volatility (24/7)
    "frxEURUSD",
    "frxGBPUSD",  # Major Forex Pairs
]

PENDING_COPILOT_SIGNALS: Dict[str, Dict[str, Any]] = {}
copilot_lock = asyncio.Lock()
ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

# ---------------------------------------------------------
# Health Check Server for Render / Cloud Hosting
# ---------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        mode_text = f"OK - Master Engine Active | Rules 78,89,90 Online | Mode: {CURRENT_TRADING_MODE}"
        self.wfile.write(mode_text.encode("utf-8"))

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

# ---------------------------------------------------------
# Telegram Bot Alerts & 1-Click Interactive Markup (Non-blocking)
# ---------------------------------------------------------
async def send_telegram_message_async(msg: str, reply_markup: dict = None):
    """Rule Check: requests.post ko asyncio.to_thread me non-blocking banaya gaya"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        await asyncio.to_thread(requests.post, url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram Async Send Error: {e}")

async def send_copilot_trade_request(sig_id: str, symbol: str, signal: str, stake: float, duration: int, duration_unit: str, reason: str):
    unit_str = "Min" if duration_unit == "m" else ("Hours" if duration_unit == "h" else "Ticks")
    msg = (
        f"🎯 *NEW SIGNAL ALERT (COPILOT)*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 *Asset:* `{symbol}`\n"
        f"🧭 *Signal:* `{signal}`\n"
        f"💰 *Kelly Stake (Rule 89):* `${stake}`\n"
        f"⏳ *Duration (Rule 90):* `{duration} {unit_str}`\n"
        f"🧠 *Reason:* _{reason}_\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👇 *ट्रेड कन्फर्म करें:*"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve Trade", "callback_data": f"APPROVE_{sig_id}"},
                {"text": "❌ Reject", "callback_data": f"REJECT_{sig_id}"}
            ]
        ]
    }
    await send_telegram_message_async(msg, reply_markup=reply_markup)

# ---------------------------------------------------------
# Capital Guardian & Rule 89 (Kelly Criterion Sizing)
# ---------------------------------------------------------
class RuleSet1CapitalGuardian:
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity = initial_balance
        self.daily_start_balance = initial_balance
        self.max_daily_loss_pct = 3.0
        self.active_positions_count = 0
        self.lock = asyncio.Lock()

    def update_balance(self, balance: float):
        self.current_balance = balance
        self.equity = balance

    def calculate_kelly_stake(self, win_rate: float = 0.60, payout_ratio: float = 0.85) -> float:
        """Rule 89: Fractional Kelly Criterion Position Sizing"""
        b = payout_ratio
        p = win_rate
        q = 1.0 - p
        
        kelly_fraction = p - (q / b)
        fractional_kelly = max(0.005, kelly_fraction * 0.25)  # Quarter-Kelly
        
        safe_risk_pct = min(2.5, max(0.5, fractional_kelly * 100.0))
        calculated_stake = self.current_balance * (safe_risk_pct / 100.0)
        return round(max(1.0, calculated_stake), 2)

    def check_safety_guards(self) -> Tuple[bool, str]:
        daily_loss = (
            (self.daily_start_balance - self.equity)
            / self.daily_start_balance
            * 100.0
        )
        if daily_loss >= self.max_daily_loss_pct:
            return False, f"🛡️ Rule 2: Daily Loss Limit Triggered ({daily_loss:.2f}%)"
        if self.active_positions_count >= 1:
            return False, "🛡️ Max Concurrent Trades Limit Reached (1 Active Max)"
        return True, "🟢 Clear"

guardian = RuleSet1CapitalGuardian()

# ---------------------------------------------------------
# Strategy Engine + Rule 78 (VPIN) + Rule 90 (ATR Duration)
# ---------------------------------------------------------
class AdvancedQuantSignalEngine:
    def calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))

    def calculate_vpin_toxicity(self, df: pd.DataFrame, bucket_size: int = 20) -> float:
        """Rule 78: Order Flow Toxicity & VPIN Approximation"""
        if len(df) < bucket_size:
            return 0.0
        
        df = df.copy()
        price_diff = df["close"].diff().fillna(0)
        
        buy_vol = np.where(price_diff > 0, df["close"], 0.0)
        sell_vol = np.where(price_diff < 0, df["close"], 0.0)
        
        imbalance = np.abs(buy_vol - sell_vol)
        total_volume = buy_vol + sell_vol + 1e-9
        
        vpin_score = np.mean(imbalance[-bucket_size:]) / np.mean(total_volume[-bucket_size:])
        return float(vpin_score)

    def calculate_adaptive_duration(self, df_5m: pd.DataFrame, symbol: str) -> Tuple[int, str]:
        """Rule 90: Volatility-Adjusted Duration with Asset Format Handling"""
        if symbol.startswith("frx"):
            return 1, "h"  # Forex pairs ke liye 1 hour standard duration

        curr = df_5m.iloc[-1]
        atr = curr.get("atr", 0.0)
        close = curr.get("close", 1.0)
        
        volatility_ratio = (atr / close) * 1000.0 if close > 0 else 1.0
        
        if volatility_ratio > 3.0:
            return 2, "m"
        elif volatility_ratio < 0.8:
            return 10, "m"
        return 5, "m"

    def calculate_indicators_5m(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        df = df_5m.copy()
        df.columns = df.columns.str.lower()
        df["ema_9"] = df["close"].ewm(span=9, adjust=False).mean()
        df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["rsi"] = self.calculate_rsi(df["close"], period=14)

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df["atr"] = ranges.max(axis=1).rolling(14).mean()
        return df

    def get_1h_trend(self, df_1h: pd.DataFrame) -> str:
        df = df_1h.copy()
        df.columns = df.columns.str.lower()
        if len(df) < 50:
            return "NEUTRAL"
        ema_50 = df["close"].ewm(span=50, adjust=False).mean()
        current_close = df["close"].iloc[-1]
        current_ema = ema_50.iloc[-1]

        if current_close > current_ema:
            return "UPTREND"
        elif current_close < current_ema:
            return "DOWNTREND"
        return "NEUTRAL"

    def evaluate_signals(
        self, symbol: str, df_1h: pd.DataFrame, df_5m: pd.DataFrame
    ) -> Tuple[str, str, int, str]:
        if df_5m is None or len(df_5m) < 25 or df_1h is None or len(df_1h) < 50:
            return "HOLD", "Insufficient Data", 5, "m"

        # Fix 1: Indicators ko pehle calculate karein taki ATR available ho
        df_5m = self.calculate_indicators_5m(df_5m)
        duration, duration_unit = self.calculate_adaptive_duration(df_5m, symbol)

        # Rule 78: Check VPIN Toxicity
        vpin = self.calculate_vpin_toxicity(df_5m)
        if vpin > 0.75:
            return "HOLD", f"Rule 78 Block: High Toxicity Flow (VPIN: {vpin:.2f})", duration, duration_unit

        trend_1h = self.get_1h_trend(df_1h)
        curr = df_5m.iloc[-1]
        prev = df_5m.iloc[-2]

        if pd.isna(curr["atr"]) or pd.isna(curr["rsi"]):
            return "HOLD", "Indicators warming up", duration, duration_unit

        ema_bullish = (prev["ema_9"] <= prev["ema_21"]) and (curr["ema_9"] > curr["ema_21"])
        if trend_1h == "UPTREND" and ema_bullish and (38 <= curr["rsi"] <= 62):
            return "CALL", f"1H Trend + 5M EMA Cross (VPIN Safe: {vpin:.2f})", duration, duration_unit

        ema_bearish = (prev["ema_9"] >= prev["ema_21"]) and (curr["ema_9"] < curr["ema_21"])
        if trend_1h == "DOWNTREND" and ema_bearish and (38 <= curr["rsi"] <= 62):
            return "PUT", f"1H Trend + 5M EMA Cross (VPIN Safe: {vpin:.2f})", duration, duration_unit

        return "HOLD", "No Clear Setup", duration, duration_unit

signal_engine = AdvancedQuantSignalEngine()

# ---------------------------------------------------------
# Execution & WebSockets
# ---------------------------------------------------------
async def fetch_deriv_candle_df(
    symbol: str, granularity: int, count: int = 100, retries: int = 3
) -> pd.DataFrame:
    for attempt in range(1, retries + 1):
        try:
            async with websockets.connect(
                ws_url,
                open_timeout=15,
                close_timeout=10,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                req = {
                    "ticks_history": symbol,
                    "adjust_start_time": 1,
                    "count": count,
                    "end": "latest",
                    "start": 1,
                    "style": "candles",
                    "granularity": granularity,
                }
                await ws.send(json.dumps(req))

                start_time = time.time()
                while time.time() - start_time < 10:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        break

                    data = json.loads(resp)
                    if "candles" in data:
                        df = pd.DataFrame(data["candles"])
                        for col in ["open", "high", "low", "close", "epoch"]:
                            if col in df.columns:
                                df[col] = df[col].astype(float)
                        return df
                    elif "error" in data:
                        return pd.DataFrame()
        except Exception:
            if attempt < retries:
                await asyncio.sleep(1.0 * attempt)
    return pd.DataFrame()

async def execute_deriv_trade(
    symbol: str, contract_type: str, stake: float, duration: int = 5, duration_unit: str = "m"
) -> bool:
    if not DERIV_API_TOKEN:
        logging.error("❌ Deriv API Token Missing.")
        return False

    try:
        async with websockets.connect(
            ws_url,
            open_timeout=15,
            close_timeout=10,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            auth_req = {"authorize": DERIV_API_TOKEN}
            await ws.send(json.dumps(auth_req))

            auth_resp = await asyncio.wait_for(ws.recv(), timeout=15)
            auth_data = json.loads(auth_resp)

            if "error" in auth_data:
                err = auth_data["error"].get("message", "Authorization failed")
                logging.error(f"❌ Deriv Auth Error: {err}")
                await send_telegram_message_async(f"❌ *Deriv Auth Error*: {err}")
                return False

            if "authorize" in auth_data:
                bal = float(auth_data["authorize"].get("balance", guardian.current_balance))
                guardian.update_balance(bal)

            buy_req = {
                "buy": 1,
                "price": stake,
                "parameters": {
                    "amount": stake,
                    "basis": "stake",
                    "contract_type": contract_type,
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": duration_unit,
                    "symbol": symbol,
                },
            }
            await ws.send(json.dumps(buy_req))
            buy_resp = await asyncio.wait_for(ws.recv(), timeout=15)
            buy_data = json.loads(buy_resp)

            if "error" in buy_data:
                err_msg = buy_data["error"].get("message", "Order Rejected")
                err_code = buy_data["error"].get("code", "N/A")
                logging.error(f"❌ Execution Error [{err_code}]: {err_msg}")
                await send_telegram_message_async(f"⚠️ *Trade Failed* on `{symbol}`: {err_msg} (`{err_code}`)")
                return False

            contract_id = buy_data["buy"]["contract_id"]
            logging.info(f"✅ Executed {contract_type} on {symbol} | ID: {contract_id}")
            unit_text = "Min" if duration_unit == "m" else ("Hours" if duration_unit == "h" else "Ticks")
            await send_telegram_message_async(
                f"🚀 *TRADE EXECUTED*\n\n"
                f"📈 *Asset:* `{symbol}`\n"
                f"🧭 *Type:* `{contract_type}`\n"
                f"💰 *Stake (Rule 89):* `${stake}`\n"
                f"⏳ *Duration (Rule 90):* `{duration} {unit_text}`\n"
                f"🆔 *Contract ID:* `{contract_id}`"
            )
            return True
    except Exception as e:
        logging.error(f"Trade Exception: {e}")
        return False

async def manage_trade_duration(duration_seconds: int):
    await asyncio.sleep(duration_seconds)
    async with guardian.lock:
        guardian.active_positions_count = max(0, guardian.active_positions_count - 1)
    logging.info("🔓 Position lock released.")

# ---------------------------------------------------------
# Telegram Copilot Listener (Non-blocking Async Loop)
# ---------------------------------------------------------
async def telegram_copilot_listener():
    global CURRENT_TRADING_MODE
    if not TELEGRAM_BOT_TOKEN:
        return

    offset = 0
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

    while True:
        try:
            # Fix 2: Non-blocking HTTP Call using asyncio.to_thread
            resp = await asyncio.to_thread(
                requests.get, url, params={"offset": offset, "timeout": 10}, timeout=12
            )
            if resp.status_code == 200:
                updates = resp.json().get("result", [])
                for u in updates:
                    offset = u["update_id"] + 1

                    if "message" in u and "text" in u["message"]:
                        chat_id = str(u["message"]["chat"]["id"])
                        text = u["message"]["text"].strip()
                        if chat_id == TELEGRAM_CHAT_ID:
                            if text.lower() == "/mode auto":
                                CURRENT_TRADING_MODE = "AUTO"
                                await send_telegram_message_async("🔄 Mode switched to: *24/7 AUTO* 🤖")
                            elif text.lower() == "/mode copilot":
                                CURRENT_TRADING_MODE = "COPILOT"
                                await send_telegram_message_async("🔄 Mode switched to: *MANUAL COPILOT* 👨‍✈️")
                            elif text.lower() == "/status":
                                await send_telegram_message_async(
                                    f"📊 *SYSTEM STATUS*\n"
                                    f"• Mode: `{CURRENT_TRADING_MODE}`\n"
                                    f"• Balance: `${guardian.current_balance}`\n"
                                    f"• Active Positions: `{guardian.active_positions_count}`\n"
                                    f"• Rules Active: `Rule 1-15, 78 (VPIN), 89 (Kelly), 90 (ATR Duration)`"
                                )

                    if "callback_query" in u:
                        cb = u["callback_query"]
                        cb_data = cb.get("data", "")
                        cb_id = cb.get("id")

                        await asyncio.to_thread(
                            requests.post,
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                            json={"callback_query_id": cb_id},
                            timeout=5
                        )

                        if cb_data.startswith("APPROVE_"):
                            sig_id = cb_data.replace("APPROVE_", "")
                            item = None
                            
                            # Fix 3: Thread-safe queue access using Lock
                            async with copilot_lock:
                                if sig_id in PENDING_COPILOT_SIGNALS:
                                    item = PENDING_COPILOT_SIGNALS.pop(sig_id)

                            if item:
                                is_safe, reason = guardian.check_safety_guards()
                                if not is_safe:
                                    await send_telegram_message_async(f"🛑 Blocked: {reason}")
                                    continue

                                async with guardian.lock:
                                    guardian.active_positions_count += 1

                                success = await execute_deriv_trade(
                                    item["symbol"], item["signal"], item["stake"], item["duration"], item["duration_unit"]
                                )
                                if success:
                                    duration_sec = item["duration"] * 3600 if item["duration_unit"] == "h" else item["duration"] * 60
                                    asyncio.create_task(manage_trade_duration(duration_sec))
                                else:
                                    async with guardian.lock:
                                        guardian.active_positions_count = max(0, guardian.active_positions_count - 1)
                            else:
                                await send_telegram_message_async("⚠️ Signal expired or already executed.")

                        elif cb_data.startswith("REJECT_"):
                            sig_i

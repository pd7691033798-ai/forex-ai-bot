import os
import time
import json
import sqlite3
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

from trend_filter import TrendFilterEngine
from smart_money import SmartMoneyEngine

trend_engine = TrendFilterEngine(ema_period=200)
smart_engine = SmartMoneyEngine()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6449682719")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "68423")  
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "pat_89e4df8ec1147df432ee86dae0e74b9f05c90819de66c69471c7882c082dca35")

# 🧪 TEST FLAG: Start hote hi 1 test trade fire karega
TEST_MODE_FORCE_TRADE = True

# -------------------------------------------------------------
# RULE SET 1: CAPITAL GUARDIAN ENGINE (RISK MANAGEMENT)
# -------------------------------------------------------------
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

    def get_1pct_stake_amount(s):
        stake = s.current_balance * (s.risk_per_trade_pct / 100.0)
        return round(max(1.0, stake), 2)  # Minimum stake $1.00

    def check_safety_guards(self) -> Tuple[bool, str]:
        daily_loss = (self.daily_start_balance - self.equity) / self.daily_start_balance * 100.0
        if daily_loss >= self.max_daily_loss_pct:
            return False, f"🛡️ Rule 2: Daily Loss Limit Triggered ({daily_loss:.2f}%)"
        
        if self.active_positions_count >= 1:
            return False, "🛡️ Max Concurrent Trades Limit Reached (1 Active Max)"

        return True, "🟢 Clear"

guardian = RuleSet1CapitalGuardian()

# -------------------------------------------------------------
# RULE SET 2: SIGNAL ENGINE
# -------------------------------------------------------------
class RuleSet2SignalEngine:
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        delta = pd.Series(prices).diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss
        return float((100 - (100 / (1 + rs))).iloc[-1])

    def calculate_macd(self, prices: List[float]) -> Tuple[float, float]:
        if len(prices) < 26:
            return 0.0, 0.0
        ema12 = pd.Series(prices).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(prices).ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return float(macd.iloc[-1]), float(signal.iloc[-1])

    def evaluate_signals(self, prices_1h: List[float], prices_15m: List[float], prices_5m: List[float], current_spread: float) -> Tuple[str, float, str]:
        # Rule Set 3 Integration
        sm_passed, sm_reason, _ = smart_engine.evaluate_smart_money_rules(prices_1h, prices_15m, current_spread)
        if not sm_passed:
            return "NONE", 0.0, f"⚠️ Rule Set 3 Blocked: {sm_reason}"

        # Rule 16 Integration (Trend Alignment)
        alignment = trend_engine.evaluate_multi_timeframe_alignment(prices_1h, prices_15m, prices_5m)
        if not alignment["allowed"]:
            return "NONE", 0.0, f"⚠️ Rule 16: {alignment['reason']}"

        trend_direction = "BULLISH" if alignment["direction"] == "BUY" else "BEARISH"

        # Rule 19: Indicator Voting System
        rsi = self.calculate_rsi(prices_5m)
        macd, signal = self.calculate_macd(prices_5m)

        votes_call = 0
        votes_put = 0

        if 30 < rsi < 50 and trend_direction == "BULLISH":
            votes_call += 1
        elif 50 < rsi < 70 and trend_direction == "BEARISH":
            votes_put += 1

        if macd > signal:
            votes_call += 1
        elif macd < signal:
            votes_put += 1

        signal_type = "NONE"
        if votes_call >= 1 and trend_direction == "BULLISH":
            signal_type = "CALL"
        elif votes_put >= 1 and trend_direction == "BEARISH":
            signal_type = "PUT"

        if signal_type == "NONE":
            return "NONE", 0.0, "⚠️ Rule 19: Indicator Voting Majority Failed"

        confidence_score = 70.0 + (votes_call if signal_type == "CALL" else votes_put) * 5.0
        return signal_type, confidence_score, f"🟢 All Rule Set 1, 2 & 3 Filters Passed"

signal_engine = RuleSet2SignalEngine()

# -------------------------------------------------------------
# WEB SERVER & TELEGRAM UTILITIES
# -------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Deriv Master Engine Online - Reused WS Active")
        except Exception as e:
            logging.error(f"Health Check Error: {e}")

    def log_message(self, format, *args):
        return

def start_dummy_web_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_telegram_message(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logging.error(f"Telegram Failed: {e}")

# -------------------------------------------------------------
# REUSED WEBSOCKET FETCHING & EXECUTION ENGINE
# -------------------------------------------------------------
async def fetch_all_timeframe_candles(symbol: str) -> Tuple[List[float], List[float], List[float]]:
    """Single WebSocket connection for high-speed candle fetching across 1H, 15M, and 5M"""
    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    try:
        async with websockets.connect(ws_url) as ws:
            # 1H Candles Request
            await ws.send(json.dumps({
                "ticks_history": symbol, "adjust_start_time": 1, "count": 210,
                "end": "latest", "style": "candles", "granularity": 3600
            }))
            res_1h = json.loads(await ws.recv())

            # 15M Candles Request
            await ws.send(json.dumps({
                "ticks_history": symbol, "adjust_start_time": 1, "count": 100,
                "end": "latest", "style": "candles", "granularity": 900
            }))
            res_15m = json.loads(await ws.recv())

            # 5M Candles Request
            await ws.send(json.dumps({
                "ticks_history": symbol, "adjust_start_time": 1, "count": 50,
                "end": "latest", "style": "candles", "granularity": 300
            }))
            res_5m = json.loads(await ws.recv())

            c_1h = [float(c["close"]) for c in res_1h.get("candles", [])]
            c_15m = [float(c["close"]) for c in res_15m.get("candles", [])]
            c_5m = [float(c["close"]) for c in res_5m.get("candles", [])]

            return c_1h, c_15m, c_5m

    except Exception as e:
        logging.error(f"Reused WS Candle Fetch Error: {e}")
        return [], [], []

async def execute_deriv_trade(symbol: str, contract_type: str, stake_amount: float):
    """Direct WebSocket Trade Execution with Guardian Checks"""
    is_safe, reason = guardian.check_safety_guards()
    if not is_safe:
        logging.warning(f"🚫 Trade Blocked by Safety Guardian: {reason}")
        send_telegram_message(f"🚫 *Trade Blocked:* {reason}")
        return

    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    try:
        async with websockets.connect(ws_url) as ws:
            # Authorize & Fetch Balance
            await ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
            auth_res = json.loads(await ws.recv())

            if "error" in auth_res:
                logging.error(f"❌ Deriv Auth Failed: {auth_res['error']['message']}")
                send_telegram_message(f"❌ *Deriv API Auth Failed:* {auth_res['error']['message']}")
                return

            current_balance = float(auth_res["authorize"]["balance"])
            guardian.update_balance(current_balance)
            logging.info(f"🟢 Authorized for {auth_res['authorize']['loginid']} | Balance: ${current_balance:.2f}")

            # Proposal
            proposal_req = {
                "proposal": 1,
                "amount": stake_amount,
                "basis": "stake",
                "contract_type": "CALL" if contract_type == "CALL" else "PUT",
                "currency": "USD",
                "duration": 5,
                "duration_unit": "m",
                "symbol": symbol
            }
            await ws.send(json.dumps(proposal_req))
            prop_res = json.loads(await ws.recv())

            if "error" in prop_res:
                logging.error(f"❌ Proposal Error: {prop_res['error']['message']}")
                send_telegram_message(f"❌ *Proposal Error:* {prop_res['error']['message']}")
                return

            proposal_id = prop_res["proposal"]["id"]
            ask_price = prop_res["proposal"]["ask_price"]

            # Buy Execution
            buy_req = {"buy": proposal_id, "price": ask_price}
            await ws.send(json.dumps(buy_req))
            buy_res = json.loads(await ws.recv())

            if "error" in buy_res:
                logging.error(f"❌ Buy Order Failed: {buy_res['error']['message']}")
                send_telegram_message(f"❌ *Buy Order Failed:* {buy_res['error']['message']}")
            else:
                contract_id = buy_res["buy"]["contract_id"]
                guardian.active_positions_count += 1
                logging.info(f"✅ Trade Executed! Contract ID: {contract_id}")
                send_telegram_message(
                    f"🎉 *DERIV DEMO TRADE EXECUTED!*\n"
                    f"• Symbol: `{symbol}`\n"
                    f"• Direction: `{contract_type}`\n"
                    f"• Stake: `${stake_amount}`\n"
                    f"• Contract ID: `{contract_id}`\n"
                    f"• Status: `ACTIVE`"
                )

    except Exception as e:
        logging.error(f"Trade Exception: {e}")
        send_telegram_message(f"❌ *Trade Exception:* `{e}`")

# -------------------------------------------------------------
# MAIN SCANNER LOOP
# -------------------------------------------------------------
async def market_scanning_loop():
    global TEST_MODE_FORCE_TRADE
    symbol = "R_100"
    logging.info(f"🔎 Real-Time Scanner Active on {symbol}...")

    # Force Test Trade Trigger on Startup
    if TEST_MODE_FORCE_TRADE:
        logging.info("🧪 Triggering Forced Test Trade on Deriv Demo...")
        test_stake = guardian.get_1pct_stake_amount()
        await execute_deriv_trade(symbol, "CALL", stake_amount=test_stake)
        TEST_MODE_FORCE_TRADE = False

    while True:
        try:
            # Reused Single WS Connection for all timeframes
            real_1h, real_15m, real_5m = await fetch_all_timeframe_candles(symbol)

            if not real_1h or not real_15m or not real_5m:
                await asyncio.sleep(15)
                continue

            current_spread = 0.4
            signal, confidence, reason = signal_engine.evaluate_signals(real_1h, real_15m, real_5m, current_spread)

            if signal in ["CALL", "PUT"] and confidence >= 70.0:
                logging.info(f"🎯 Valid Signal Found: {signal} ({confidence:.1f}%) | {reason}")
                stake = guardian.get_1pct_stake_amount()
                await execute_deriv_trade(symbol, signal, stake_amount=stake)

        except Exception as e:
            logging.error(f"Scanner Loop Error: {e}")

        await asyncio.sleep(60)

async def main():
    threading.Thread(target=start_dummy_web_server, daemon=True).start()
    send_telegram_message("🤖 *Master Bot Engine Online:* Safety Guardian & Reused WS Active!")
    asyncio.create_task(market_scanning_loop())
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())

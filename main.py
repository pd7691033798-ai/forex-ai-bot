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

from trend_filter import TrendFilterEngine
from smart_money import SmartMoneyEngine

trend_engine = TrendFilterEngine(ema_period=200)
smart_engine = SmartMoneyEngine()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# Environment Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6449682719")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "68423")  
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "pat_5c81fda0a57ef6c95833fc2a51428dd0cd828a2ca5dfaa84f259086d55d0282b")

SYMBOLS_TO_SCAN = ["R_10", "R_25", "R_50", "R_75", "R_100"]

def send_telegram_message(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=5
        )
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

class RuleSet2SignalEngine:
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1: return 50.0
        delta = pd.Series(prices).diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss
        return float((100 - (100 / (1 + rs))).iloc[-1])

    def calculate_macd(self, prices: List[float]) -> Tuple[float, float]:
        if len(prices) < 26: return 0.0, 0.0
        ema12 = pd.Series(prices).ewm(span=12, adjust=False).mean()
        ema26 = pd.Series(prices).ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        return float(macd.iloc[-1]), float(signal.iloc[-1])

    def evaluate_signals(self, prices_1h: List[float], prices_15m: List[float], prices_5m: List[float], current_spread: float) -> Tuple[str, float, str]:
        sm_passed, sm_reason, _ = smart_engine.evaluate_smart_money_rules(prices_1h, prices_15m, current_spread)
        if not sm_passed: return "NONE", 0.0, f"⚠️ Rule Set 3 Blocked: {sm_reason}"

        alignment = trend_engine.evaluate_multi_timeframe_alignment(prices_1h, prices_15m, prices_5m)
        if not alignment["allowed"]:
            return "NONE", 0.0, f"⚠️ Trend Filter: {alignment['reason']}"

        trend_direction = "BULLISH" if alignment["direction"] == "BUY" else "BEARISH"

        rsi = self.calculate_rsi(prices_5m)
        macd, signal = self.calculate_macd(prices_5m)

        votes_call, votes_put = 0, 0
        if 35 < rsi < 55 and trend_direction == "BULLISH": votes_call += 1
        elif 45 < rsi < 65 and trend_direction == "BEARISH": votes_put += 1
        
        if macd > signal: votes_call += 1
        elif macd < signal: votes_put += 1

        signal_type = "NONE"
        if votes_call >= 1 and trend_direction == "BULLISH": signal_type = "CALL"
        elif votes_put >= 1 and trend_direction == "BEARISH": signal_type = "PUT"

        if signal_type == "NONE": return "NONE", 0.0, "⚠️ Indicator Confluence Pending"

        confidence_score = 65.0 + (votes_call if signal_type == "CALL" else votes_put) * 5.0
        return signal_type, confidence_score, f"🟢 Practical Trend Alignment Passed"

signal_engine = RuleSet2SignalEngine()

async def fetch_all_timeframe_candles(symbol: str) -> Tuple[List[float], List[float], List[float]]:
    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"ticks_history": symbol, "adjust_start_time": 1, "count": 210, "end": "latest", "style": "candles", "granularity": 3600}))
            res_1h = json.loads(await ws.recv())
            await ws.send(json.dumps({"ticks_history": symbol, "adjust_start_time": 1, "count": 100, "end": "latest", "style": "candles", "granularity": 900}))
            res_15m = json.loads(await ws.recv())
            await ws.send(json.dumps({"ticks_history": symbol, "adjust_start_time": 1, "count": 50, "end": "latest", "style": "candles", "granularity": 300}))
            res_5m = json.loads(await ws.recv())
            
            c_1h = [float(c["close"]) for c in res_1h.get("candles", [])]
            c_15m = [float(c["close"]) for c in res_15m.get("candles", [])]
            c_5m = [float(c["close"]) for c in res_5m.get("candles", [])]

            if len(c_1h) < 20 or len(c_15m) < 20 or len(c_5m) < 20:
                return [], [], []

            return c_1h, c_15m, c_5m
    except Exception as e:
        return [], [], []

async def release_position_lock_after_delay(delay_seconds: int = 300):
    await asyncio.sleep(delay_seconds)
    guardian.active_positions_count = max(0, guardian.active_positions_count - 1)
    logging.info("🔓 Trade Duration Finished: Position Lock Released")

async def execute_deriv_trade(symbol: str, contract_type: str, stake_amount: float) -> bool:
    is_safe, reason = guardian.check_safety_guards()
    if not is_safe:
        logging.warning(f"🚫 Trade Blocked by Guardian: {reason}")
        return False

    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    try:
        async with websockets.connect(ws_url) as ws:
            # 1. Authorize Token
            await ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
            auth_res = json.loads(await ws.recv())
            if "error" in auth_res:
                err_msg = auth_res["error"]["message"]
                logging.error(f"❌ Deriv Auth Error: {err_msg}")
                send_telegram_message(f"❌ Deriv Auth Failed: {err_msg}\nCheck API Token on Deriv!")
                return False
            
            guardian.update_balance(float(auth_res["authorize"]["balance"]))

            # 2. Contract Proposal Request
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
                err_msg = prop_res["error"]["message"]
                logging.error(f"❌ Proposal Error: {err_msg}")
                send_telegram_message(f"❌ Deriv Proposal Rejected: {err_msg}")
                return False
            
            # 3. Buy Contract Request
            buy_req = {"buy": prop_res["proposal"]["id"], "price": prop_res["proposal"]["ask_price"]}
            await ws.send(json.dumps(buy_req))
            buy_res = json.loads(await ws.recv())
            
            if "error" in buy_res:
                err_msg = buy_res["error"]["message"]
                logging.error(f"❌ Buy Execution Error: {err_msg}")
                send_telegram_message(f"❌ Trade Buy Failed: {err_msg}")
                return False
            else:
                guardian.active_positions_count += 1
                asyncio.create_task(release_position_lock_after_delay(300))
                logging.info(f"✅ Trade Successfully Placed on Deriv: {symbol} {contract_type}")
                send_telegram_message(
                    f"🎉 REAL-CONDITIONS DEMO TRADE EXECUTED!\n"
                    f"• Asset: {symbol}\n"
                    f"• Type: {contract_type}\n"
                    f"• Stake: ${stake_amount}\n"
                    f"• Duration: 5 Minutes"
                )
                return True
    except Exception as e:
        logging.error(f"Trade Execution Exception: {e}")
        send_telegram_message(f"⚠️ Execution Exception: {str(e)}")
        return False

async def market_scanning_loop():
    logging.info("🔎 Real-Condition Multi-Asset Scanner Active...")
    while True:
        for symbol in SYMBOLS_TO_SCAN:
            try:
                real_1h, real_15m, real_5m = await fetch_all_timeframe_candles(symbol)
                if not real_1h or not real_15m or not real_5m:
                    continue

                signal, confidence, reason = signal_engine.evaluate_signals(real_1h, real_15m, real_5m, 0.4)

                if signal in ["CALL", "PUT"] and confidence >= 65.0:
                    logging.info(f"🎯 Valid Trade Signal on {symbol}: {signal} ({confidence:.1f}%)")
                    stake = guardian.get_1pct_stake_amount()
                    executed = await execute_deriv_trade(symbol, signal, stake_amount=stake)
                    if executed:
                        logging.info("⏸️ Trade Placed! Pausing scanner for 300 seconds...")
                        await asyncio.sleep(300)  # 5 मिनट तक स्कैनिंग रोकें ताकि पिछला ट्रेड पूरा हो

            except Exception as e:
                logging.error(f"Scanner Loop Error on {symbol}: {e}")
            
            await asyncio.sleep(5)

        await asyncio.sleep(30)

async def main():
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.getenv("PORT", 10000))), HealthCheckHandler).serve_forever(), daemon=True).start()
    send_telegram_message("🚀 Multi-Asset Real Condition Training Engine Started! Scanning 5 Volatility Indices...")
    asyncio.create_task(market_scanning_loop())
    while True: await asyncio.sleep(1)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"Training Engine Online")

if __name__ == "__main__":
    asyncio.run(main())

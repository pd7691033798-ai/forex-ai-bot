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
from news_guard import EconomicNewsGuard

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# Global Engines
trend_engine = TrendFilterEngine(ema_period=200)
smart_engine = SmartMoneyEngine()
news_guard = EconomicNewsGuard()

# Configuration & Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6449682719")
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "68423")
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "pat_007694a0cbf4459dbe3d9d3dce0bcc61436142c409443bc11f3e5775ebedab08").strip()

# Multi-Asset Scan Universe (Forex, Gold, Crypto, Volatility Indices)
SYMBOLS_TO_SCAN = [
    "R_10", "R_25", "R_50", "R_75", "R_100",  # Deriv Synthetic Volatility
    "frxEURUSD", "frxGBPUSD", "frxXAUUSD", "cryBTCUSD"  # Forex, Gold, Crypto
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

class FlexibleSignalEngine:
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
        # 1. Economic News Guard Check
        is_news, news_reason = news_guard.is_high_impact_news_near()
        if is_news:
            return "NONE", 0.0, news_reason

        # 2. Smart Money Concepts (SMC) Rule Set 3 Check (Handled safely for tuple format)
        smc_res = smart_engine.evaluate_smart_money_rules(prices_1h, prices_15m, current_spread)
        sm_passed, sm_reason = smc_res[0], smc_res[1]
        sm_boost = smc_res[2] if len(smc_res) > 2 and isinstance(smc_res[2], (int, float)) else 0.0

        if not sm_passed:
            return "NONE", 0.0, f"⚠️ Rule Set 3 Blocked: {sm_reason}"

        # 3. Multi-Timeframe Trend Alignment Check
        alignment = trend_engine.evaluate_multi_timeframe_alignment(prices_1h, prices_15m, prices_5m)
        if not alignment["allowed"]:
            return "NONE", 0.0, f"⚠️ Trend Filter: {alignment['reason']}"

        trend_direction = "BULLISH" if alignment["direction"] == "BUY" else "BEARISH"

        rsi = self.calculate_rsi(prices_5m)
        macd, signal = self.calculate_macd(prices_5m)

        base_confidence = 60.0
        votes_call, votes_put = 0, 0

        if 35 < rsi < 60 and trend_direction == "BULLISH": votes_call += 1
        elif 40 < rsi < 65 and trend_direction == "BEARISH": votes_put += 1
        
        if macd > signal: votes_call += 1
        elif macd < signal: votes_put += 1

        signal_type = "NONE"
        if votes_call >= 1 and trend_direction == "BULLISH": signal_type = "CALL"
        elif votes_put >= 1 and trend_direction == "BEARISH": signal_type = "PUT"

        # Calculate Final Flexible Confidence Score (Base + Votes + SMC Boost)
        confidence_score = base_confidence + (votes_call * 10 if signal_type == "CALL" else votes_put * 10) + sm_boost

        # Flexible Threshold set to 80% Confidence for High-Quality Weekly Trades
        if confidence_score < 80.0 or signal_type == "NONE":
            return "NONE", confidence_score, "⚠️ Confluence Score below 80% Threshold"

        return signal_type, confidence_score, "🟢 Signal Validated (SMC + Multi-Asset)"

signal_engine = FlexibleSignalEngine()

# Deriv API WebSocket Connection
ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

async def fetch_deriv_candles(symbol: str, granularity: int, count: int = 100) -> List[float]:
    try:
        async with websockets.connect(ws_url) as ws:
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
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            data = json.loads(resp)
            if "candles" in data:
                return [float(c["close"]) for c in data["candles"]]
    except Exception as e:
        logging.error(f"Live Data Fetch Error on {symbol} ({granularity}s): {e}")
    return []

async def execute_deriv_trade(symbol: str, contract_type: str, stake: float) -> bool:
    try:
        async with websockets.connect(ws_url) as ws:
            # 1. Authorize Token
            auth_req = {"authorize": DERIV_API_TOKEN}
            await ws.send(json.dumps(auth_req))
            auth_resp = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_data = json.loads(auth_resp)

            if "error" in auth_data:
                err_msg = auth_data["error"]["message"]
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
            buy_resp = await asyncio.wait_for(ws.recv(), timeout=10)
            buy_data = json.loads(buy_resp)

            if "error" in buy_data:
                logging.error(f"❌ Trade Execution Error: {buy_data['error']}")
                send_telegram_message(f"⚠️ *Trade Failed* on {symbol}: {buy_data['error']['message']}")
                return False

            contract_id = buy_data["buy"]["contract_id"]
            logging.info(f"✅ Trade Placed Successfully on {symbol}! Contract ID: {contract_id}")
            send_telegram_message(f"🚀 *HIGH CONFIDENCE TRADE EXECUTED*\n\n*Asset:* {symbol}\n*Type:* {contract_type}\n*Stake:* ${stake}\n*Contract ID:* {contract_id}\n*Duration:* 5 Min")
            return True
    except Exception as e:
        logging.error(f"Trade Execution Exception: {e}")
        return False

async def market_scanning_loop():
    logging.info("🔎 Multi-Asset Smart-Balance Scanner Active...")
    send_telegram_message("🚀 *Multi-Asset Smart-Balance Engine Online*\nScanning Synthetic Volatility, Forex, Gold & Crypto Assets @ 80% Flexible Threshold!")

    while True:
        try:
            is_safe, safety_reason = guardian.check_safety_guards()
            if not is_safe:
                logging.warning(f"Safety Guard Active: {safety_reason}")
                await asyncio.sleep(15)
                continue

            for symbol in SYMBOLS_TO_SCAN:
                prices_1h = await fetch_deriv_candles(symbol, 3600, 100)
                prices_15m = await fetch_deriv_candles(symbol, 900, 100)
                prices_5m = await fetch_deriv_candles(symbol, 300, 100)

                if len(prices_1h) < 30 or len(prices_15m) < 30 or len(prices_5m) < 30:
                    continue

                current_spread = 0.0001
                signal, confidence, reason = signal_engine.evaluate_signals(prices_1h, prices_15m, prices_5m, current_spread)

                if signal in ["CALL", "PUT"] and confidence >= 80.0:
                    logging.info(f"🎯 Valid Trade Signal on {symbol}: {signal} ({confidence:.1f}%)")
                    stake = guardian.get_1pct_stake_amount()
                    
                    guardian.active_positions_count += 1
                    success = await execute_deriv_trade(symbol, signal, stake)
                    
                    if success:
                        await asyncio.sleep(300) # Wait 5 minutes for trade outcome
                    
                    guardian.active_positions_count = max(0, guardian.active_positions_count - 1)

        except Exception as e:
            logging.error(f"Market Scanning Loop Error: {e}")
        
        await asyncio.sleep(5)

def main():
    t = threading.Thread(target=run_health_server, daemon=True)
    t.start()

    logging.info("🚀 Starting Complete Multi-Asset Smart-Balance Engine...")
    asyncio.run(market_scanning_loop())

if __name__ == "__main__":
    main()

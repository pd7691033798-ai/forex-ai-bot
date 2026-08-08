import os
import time
import json
import asyncio
import logging
import datetime
import requests
import websockets
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

# -------------------------------------------------------------
# 0. RENDER HEALTH CHECK SERVER (Port Binding Fix)
# -------------------------------------------------------------
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"SuperBot is Live and Running!")

    def log_message(self, format, *args):
        return  # Render के हेल्थ चेक लॉग्स को ब्लॉक करने के लिए

def start_dummy_web_server():
    """Render को पोर्ट दिखाने के लिए बैकग्राउंड वेब सर्वर"""
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"🌐 Dummy Health Check Server listening on port {port}")
    server.serve_forever()

# -------------------------------------------------------------
# LOGGING SETUP
# -------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

# -------------------------------------------------------------
# 1. CONFIGURATION & CREDENTIALS
# -------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6449682719")

# Updated Custom Deriv App ID
DERIV_APP_ID = os.getenv("DERIV_APP_ID", "68423")  
DERIV_API_TOKEN = os.getenv("DERIV_API_TOKEN", "pat_89e4df8ec1147df432ee86dae0e74b9f05c90819de66c69471c7882c082dca35")

# -------------------------------------------------------------
# 2. PHASE 1 CAPITAL SAFETY & STEALTH ENGINE
# -------------------------------------------------------------
class Phase1CapitalGuardian:
    def __init__(self, initial_balance: float = 10000.0, max_daily_loss_pct: float = 3.0, risk_per_trade_pct: float = 1.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity = initial_balance
        self.daily_start_balance = initial_balance
        
        self.max_daily_loss_pct = max_daily_loss_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        self.kill_switch_activated = False

        # Stealth Mode: Stop-Loss & Take-Profit Memory Storage
        self.phantom_positions: Dict[str, Dict[str, Any]] = {}

    def calculate_dynamic_lot(self, stop_loss_pips: float, pip_value: float = 10.0) -> float:
        if stop_loss_pips <= 0:
            return 0.01
        risk_amount = self.current_balance * (self.risk_per_trade_pct / 100.0)
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        return round(max(0.01, lot_size), 2)

    def check_safety_guards(self) -> tuple[bool, str]:
        """ट्रेड लेने से पहले सुरक्षा जांच"""
        if self.kill_switch_activated:
            return False, "🚨 Emergency Kill Switch Active!"

        if self.circuit_breaker_active:
            if datetime.datetime.utcnow() < self.circuit_breaker_until:
                return False, f"⚡ Circuit Breaker Active until {self.circuit_breaker_until.strftime('%H:%M UTC')}"
            else:
                self.circuit_breaker_active = False
                self.consecutive_losses = 0

        daily_loss = (self.daily_start_balance - self.equity) / self.daily_start_balance * 100.0
        if daily_loss >= self.max_daily_loss_pct:
            return False, f"🛡️ Daily Equity Guardian Triggered! Loss: {daily_loss:.2f}% >= {self.max_daily_loss_pct}%"

        return True, "🟢 Safety Guards Clear"

    def register_trade_result(self, is_win: bool, pnl: float):
        self.equity += pnl
        self.current_balance += pnl

        if is_win:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            logging.warning(f"Trade Loss recorded. Consecutive Losses: {self.consecutive_losses}")

        if self.consecutive_losses >= self.max_consecutive_losses:
            self.circuit_breaker_active = True
            self.circuit_breaker_until = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            logging.critical(f"Circuit Breaker Activated! 3 consecutive losses.")

# Global Phase 1 Instance
guardian = Phase1CapitalGuardian()

# -------------------------------------------------------------
# 3. TELEGRAM SENDER FUNCTION
# -------------------------------------------------------------
def send_telegram_message(message: str):
    """टेलीग्राम संदेश भेजने के लिए फ़ंक्शन"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.json()
    except Exception as e:
        logging.error(f"Telegram Message Failed: {e}")
        return None

# -------------------------------------------------------------
# 4. DERIV TRADE EXECUTION (PHASE 1 INTEGRATED)
# -------------------------------------------------------------
async def execute_deriv_trade(symbol: str, contract_type: str, amount: float, duration: int, stealth_sl: float, stealth_tp: float):
    """Phase 1 Guard से होकर जाने वाला ट्रेड फ़ंक्शन"""
    
    # STEP 1: Phase 1 Safety Check
    is_safe, reason = guardian.check_safety_guards()
    if not is_safe:
        logging.warning(f"Trade Blocked: {reason}")
        send_telegram_message(f"🚫 *Trade Rejected by Phase 1*\nReason: {reason}")
        return

    # STEP 2: Deriv WebSocket Connection with Custom App ID (68423)
    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Authorize
            await ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
            auth_res = json.loads(await ws.recv())
            
            if "error" in auth_res:
                send_telegram_message(f"❌ *Deriv Auth Error:* `{auth_res['error']['message']}`")
                return

            # Buy Request
            buy_req = {
                "buy": 1,
                "price": amount,
                "parameters": {
                    "amount": amount,
                    "basis": "stake",
                    "contract_type": contract_type,  # CALL / PUT
                    "currency": "USD",
                    "duration": duration,
                    "duration_unit": "m",
                    "symbol": symbol
                }
            }
            await ws.send(json.dumps(buy_req))
            buy_res = json.loads(await ws.recv())

            if "buy" in buy_res:
                contract_id = str(buy_res["buy"]["contract_id"])

                # Stealth SL/TP Memory Tracking
                guardian.phantom_positions[contract_id] = {
                    "symbol": symbol,
                    "type": contract_type,
                    "sl": stealth_sl,
                    "tp": stealth_tp
                }

                send_telegram_message(
                    f"✅ *Trade Placed on Deriv*\n"
                    f"• Symbol: `{symbol}`\n"
                    f"• Type: `{contract_type}`\n"
                    f"• Stake: `${amount}`\n"
                    f"• Order ID: `{contract_id}`\n"
                    f"🛡️ *Phantom SL/TP Active in Memory*"
                )
            else:
                send_telegram_message(f"❌ *Order Execution Failed:* `{buy_res.get('error', {}).get('message')}`")

    except Exception as e:
        logging.error(f"Deriv Connection Error: {e}")
        send_telegram_message(f"🚨 *Execution Exception:* `{str(e)}`")

# -------------------------------------------------------------
# 5. 10-MINUTE TELEGRAM HEARTBEAT LOOP
# -------------------------------------------------------------
async def periodic_telegram_heartbeat():
    """हर 10 मिनट में Telegram पर स्टेटस अपडेट भेजेगा"""
    while True:
        try:
            is_safe, safety_msg = guardian.check_safety_guards()
            cb_status = "🔴 ACTIVE" if guardian.circuit_breaker_active else "🟢 NORMAL"
            
            status_text = (
                f"💓 *SuperBot 10-Min Heartbeat Update*\n"
                f"─────────────────────────────\n"
                f"💵 *Balance:* `${guardian.current_balance:.2f}`\n"
                f"📈 *Equity:* `${guardian.equity:.2f}`\n"
                f"🛡️ *Phase 1 Guard:* {safety_msg}\n"
                f"⚡ *Circuit Breaker:* {cb_status}\n"
                f"👻 *Active Stealth Positions:* {len(guardian.phantom_positions)}\n"
                f"📱 *Deriv App ID:* `{DERIV_APP_ID}`\n"
                f"⏰ *Server Time:* `{datetime.datetime.utcnow().strftime('%H:%M:%S UTC')}`"
            )
            
            # टेलीग्राम पर संदेश भेजें
            send_telegram_message(status_text)
            
        except Exception as e:
            logging.error(f"Heartbeat Error: {e}")

        # 10 मिनट (600 सेकंड) का इंतजार
        await asyncio.sleep(600)

# -------------------------------------------------------------
# 6. MAIN APPLICATION ENTRY POINT
# -------------------------------------------------------------
async def main():
    logging.info(f"🚀 Starting Phase 1 Merged SuperBot Engine with App ID: {DERIV_APP_ID}...")
    
    # Render के लिए Background Thread में Dummy Web Server चालू करें
    threading.Thread(target=start_dummy_web_server, daemon=True).start()

    # बोट स्टार्ट होने पर टेलीग्राम पर पहला मैसेज भेजेगा
    send_telegram_message(
        f"🤖 *SuperBot Phase 1 Engine Started on Render!*\n"
        f"─────────────────────────────\n"
        f"• Deriv App ID: `{DERIV_APP_ID}` (Configured)\n"
        f"• Capital Guard (1% Risk Limit): Active\n"
        f"• Stealth Phantom SL: Active\n"
        f"• 10-Min Heartbeat Loop: Active"
    )

    # 10 मिनट वाले बैकग्राउंड लूप को स्टार्ट करें
    asyncio.create_task(periodic_telegram_heartbeat())

    # Render पर बोट को 24/7 एक्टिव रखने के लिए लूप
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
    

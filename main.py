import os
import threading
import json
import time
import requests
import websocket
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================================================
# 1. CONFIGURATION (यहाँ अपनी सही डिटेल्स भरें)
# =========================================================
DERIV_API_TOKEN =  "pat_89e4df8ec1147df432ee86dae0e74b9f05c90819de66c69471c7882c082dca35"
# 👈 अपना Deriv API Token डालें
APP_ID = "1089"                                 # 👈 Deriv Numeric App ID (1089 Standard है)

TELEGRAM_BOT_TOKEN = "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c"  # 👈 अपना Telegram Bot Token लिखें
TELEGRAM_CHAT_ID = "6449682719"      # 👈 अपना Telegram Chat ID लिखें

# =========================================================
# 2. TELEGRAM ALERT SENDER
# =========================================================
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=10)
        print("📲 Telegram Alert Sent Successfully!", flush=True)
    except Exception as e:
        print(f"⚠️ Telegram Error: {e}", flush=True)

# =========================================================
# 3. DERIV AUTO-TRADE EXECUTION
# =========================================================
def send_deriv_trade(symbol, trade_type, amount=10):
    print(f"👉 EXECUTION TRIGGERED FOR: {symbol} | {trade_type}", flush=True)

    def on_open(ws):
        print("🔗 WebSocket Connected! Authorizing...", flush=True)
        ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))

    def on_message(ws, message):
        data = json.loads(message)
        print(f"📩 Deriv Response: {data}", flush=True)

        if data.get("msg_type") == "authorize":
            if "error" in data:
                print(f"❌ AUTH ERROR: {data['error']['message']}", flush=True)
                send_telegram_message(f"❌ <b>Deriv Auth Failure:</b> {data['error']['message']}")
                ws.close()
            else:
                print("✅ Authorized! Sending Proposal...", flush=True)
                deriv_symbol = "frxXAUUSD" if "XAU" in symbol else "frxEURUSD"
                contract_type = "CALL" if trade_type == "BUY" else "PUT"
                
                proposal_req = {
                    "buy": 1, 
                    "price": amount,
                    "parameters": {
                        "amount": amount, 
                        "basis": "stake",
                        "contract_type": contract_type, 
                        "currency": "USD",
                        "duration": 5, 
                        "duration_unit": "m", 
                        "symbol": deriv_symbol
                    }
                }
                ws.send(json.dumps(proposal_req))

        elif data.get("msg_type") == "buy":
            if "error" in data:
                print(f"❌ TRADE ERROR: {data['error']['message']}", flush=True)
                send_telegram_message(f"❌ <b>Trade Exec Failed:</b> {data['error']['message']}")
            else:
                trade_id = data['buy']['transaction_id']
                print(f"🚀 SUCCESS! Trade Placed ID: {trade_id}", flush=True)
                send_telegram_message(f"🚀 <b>Auto-Trade Executed!</b>\n\n<b>Symbol:</b> {symbol}\n<b>Action:</b> {trade_type}\n<b>Trade ID:</b> {trade_id}")
            ws.close()

    def on_error(ws, error):
        print(f"⚠️ WS ERROR: {error}", flush=True)

    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
    ws.run_forever()

# =========================================================
# 4. ML MACHINE LEARNING & VOLATILITY SHIELD ANALYSIS
# =========================================================
def analyze_with_ml():
    print("📊 Fetching Market Data & Training ML Model...", flush=True)
    try:
        ticker = yf.Ticker("GC=F")
        df = ticker.history(period="5d", interval="5m")
        if df.empty or len(df) < 50:
            return

        df['Returns'] = df['Close'].pct_change()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        df['High_Low'] = df['High'] - df['Low']
        df['ATR'] = df['High_Low'].rolling(window=14).mean()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()

        df['Target'] = 0
        df.loc[(df['RSI'] < 35) & (df['Close'] > df['SMA_20']), 'Target'] = 1
        df.loc[(df['RSI'] > 65) & (df['Close'] < df['SMA_20']), 'Target'] = -1

        df = df.dropna()
        X = df[['RSI', 'ATR', 'Returns', 'High_Low']]
        y = df['Target']

        if len(X) < 20:
            return

        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        latest_features = X.iloc[[-1]]
        prediction = model.predict(latest_features)[0]

        last_price = df['Close'].iloc[-1]
        current_rsi = df['RSI'].iloc[-1]
        current_atr = df['ATR'].iloc[-1]
        avg_atr = df['ATR'].mean()

        # Volatility Shield (News/War Protection)
        is_high_volatility = current_atr > (avg_atr * 2.5)
        if is_high_volatility:
            send_telegram_message(f"🚨 <b>NEWS/WAR SHIELD ACTIVE (GOLD)</b>\nPrice: ${last_price:.2f}\nVolatility Spike Detected! Auto-Trades Paused.")
            return

        signal = "HOLD"
        if prediction == 1:
            signal = "BUY"
        elif prediction == -1:
            signal = "SELL"

        msg = f"🧠 <b>SUPER BOT ML REPORT (GOLD)</b>\nPrice: ${last_price:.2f}\nRSI: {current_rsi:.1f}\nATR: {current_atr:.2f}\nML Signal: <b>{signal}</b>"
        send_telegram_message(msg)

        if signal in ["BUY", "SELL"]:
            send_deriv_trade("XAUUSD", signal)

    except Exception as e:
        print(f"⚠️ ML Engine Error: {e}", flush=True)

# =========================================================
# 5. BACKGROUND ENGINE LOOP
# =========================================================
def telegram_bot_loop():
    print("🤖 Super Bot Background Loop Active...", flush=True)
    send_telegram_message("🤖 <b>Super Bot Online!</b>\nMachine Learning Analysis & Volatility Shield Active.")
    
    while True:
        try:
            analyze_with_ml()
            time.sleep(600)  # हर 10 मिनट पर चेक करेगा
        except Exception as e:
            print(f"⚠️ Loop Error: {e}", flush=True)
            time.sleep(30)

# =========================================================
# 6. WEB INTERFACE & RUNNER
# =========================================================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Super Bot Dashboard</title>
        <style>
            body { background: #0d1117; color: white; text-align: center; font-family: sans-serif; padding: 20px; }
            .card { background: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 20px; }
            .btn { width: 45%; padding: 15px; margin: 5px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; color: white; }
            .btn-buy { background: #238636; }
            .btn-sell { background: #da3633; }
        </style>
    </head>
    <body>
        <h2>🤖 Super Bot Control Center</h2>
        <div class="card">
            <h4>Select Market</h4>
            <select id="symbolSelect" style="padding: 10px; width: 80%; background: #21262d; color: white; border-radius: 5px;">
                <option value="XAUUSD">GOLD (XAU/USD)</option>
                <option value="EURUSD">EUR/USD</option>
            </select>
        </div>
        <div class="card">
            <h4>Manual Trade Override</h4>
            <button class="btn btn-buy" onclick="triggerTrade('BUY')">BUY 📈</button>
            <button class="btn btn-sell" onclick="triggerTrade('SELL')">SELL 📉</button>
        </div>
        <script>
            function triggerTrade(action) {
                let symbol = document.getElementById('symbolSelect').value;
                alert("Sending " + action + " order for " + symbol + "...");
                fetch('/execute-trade', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({symbol: symbol, action: action})
                });
            }
        </script>
    </body>
    </html>
    """

@app.route('/execute-trade', methods=['POST'])
def execute_trade_route():
    data = request.json
    symbol = data.get('symbol', 'XAUUSD')
    action = data.get('action', 'BUY')
    threading.Thread(target=send_deriv_trade, args=(symbol, action)).start()
    return jsonify({"status": "Request Sent"})

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=telegram_bot_loop, daemon=True).start()
    run_web_server()

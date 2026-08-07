import os
import threading
import json
import websocket
from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================================================
# 1. DERIV API AUTO-TRADE CONFIGURATION
# =========================================================
DERIV_API_TOKEN = "YOUR_DERIV_API_TOKEN_HERE"  # 👈 यहाँ अपना Deriv API Token डालें
APP_ID = "pat_504c2a11cdff0965d23fa7cdcc496f8ab42756562baeaca3d5a04490b29ea9a3"  # Deriv Default App ID
.send(json.dumps(proposal_req))

        def send_deriv_trade(symbol, trade_type, amount=10):
    print(f"👉 EXECUTION TRIGGERED FOR: {symbol} | {trade_type}", flush=True)

    def on_open(ws):
        print("🔗 WebSocket Connected! Authorizing Token...", flush=True)
        ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))

    def on_message(ws, message):
        data = json.loads(message)
        print(f"📩 Deriv Response: {data}", flush=True)  # <-- इससे पूरा Error दिखेगा

        if data.get("msg_type") == "authorize":
            if "error" in data:
                print(f"❌ AUTH ERROR: {data['error']['message']}", flush=True)
                ws.close()
            else:
                print("✅ Token Authorized! Sending Order Proposal...", flush=True)
                deriv_symbol = "frxXAUUSD" if "XAU" in symbol else "frxEURUSD"
                contract_type = "CALL" if trade_type == "BUY" else "PUT"
                ws.send(json.dumps({
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
                }))

        elif data.get("msg_type") == "buy":
            if "error" in data:
                print(f"❌ TRADE ERROR: {data['error']['message']}", flush=True)
            else:
                print(f"🚀 SUCCESS! Trade Placed. ID: {data['buy']['transaction_id']}", flush=True)
            ws.close()

    def on_error(ws, error):
        print(f"⚠️ WS ERROR: {error}", flush=True)

    ws = websocket.WebSocketApp(
        f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}",
        on_open=on_open, 
        on_message=on_message,
        on_error=on_error
    )
    ws.run_forever()


# =========================================================
# 2. WEB INTERFACE (Trading Terminal + TradingView Chart)
# =========================================================
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Deriv AI Auto-Trading Terminal</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 10px; text-align: center; }
            .container { max-width: 600px; margin: 0 auto; }
            .card { background: #161b22; border-radius: 12px; padding: 12px; margin-bottom: 12px; border: 1px solid #30363d; }
            .btn-container { display: flex; gap: 10px; justify-content: center; margin-top: 10px; }
            .btn { flex: 1; padding: 14px; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; cursor: pointer; color: white; }
            .btn-buy { background-color: #238636; }
            .btn-sell { background-color: #da3633; }
            select { width: 100%; padding: 10px; background: #21262d; color: white; border: 1px solid #30363d; border-radius: 6px; font-size: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h3>🤖 AI Pro Trading Terminal</h3>
            
            <div class="card">
                <span style="color:#3fb950; font-weight:bold;">● Status: Connected to Deriv Cloud Server</span>
            </div>

            <!-- TradingView Live Chart Widget -->
            <div class="card" style="padding: 5px; height: 380px;">
                <div class="tradingview-widget-container" style="height:100%;width:100%">
                  <div id="tradingview_chart" style="height:calc(100% - 32px);width:100%"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                  <script type="text/javascript">
                  new TradingView.widget({
                  "autosize": true,
                  "symbol": "OANDA:XAUUSD",
                  "interval": "15",
                  "timezone": "Asia/Kolkata",
                  "theme": "dark",
                  "style": "1",
                  "locale": "en",
                  "enable_publishing": false,
                  "hide_side_toolbar": false,
                  "container_id": "tradingview_chart"
                });
                  </script>
                </div>
            </div>

            <!-- Auto Trade Panel -->
            <div class="card">
                <h4>⚡ Direct Deriv Auto-Execution</h4>
                <select id="pairSelect">
                    <option value="XAUUSD">GOLD (XAU/USD)</option>
                    <option value="EURUSD">EUR/USD</option>
                </select>
                <div class="btn-container">
                    <button class="btn btn-buy" onclick="executeTrade('BUY')">BUY 📈</button>
                    <button class="btn btn-sell" onclick="executeTrade('SELL')">SELL 📉</button>
                </div>
            </div>
        </div>

        <script>
            function executeTrade(action) {
                let symbol = document.getElementById('pairSelect').value;
                alert("Sending " + action + " order for " + symbol + " to Deriv Server...");
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
    
    # Run in Background Thread so the Web App stays fast
    threading.Thread(target=send_deriv_trade, args=(symbol, action)).start()
    return jsonify({"status": "Execution Started"})

# =========================================================
# SERVER AND BOT RUNNER (FIXED)
# =========================================================
def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    # use_reloader=False से पोर्ट ब्लॉक होने का एरर खत्म हो जाएगा
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    # 1. Telegram Bot को बैकग्राउंड में चलाएं
    if 'telegram_bot_loop' in globals():
        threading.Thread(target=telegram_bot_loop, daemon=True).start()
    
    # 2. Web Server को Main Thread में चलाएं
    run_web_server()
    

# =========================================================
# 3. YOUR TELEGRAM BOT CODE (आपका पुराना कोड नीचे ही रहेगा)
# =========================================================

# (यहाँ आपका पुराना yfinance, RSI, और Telegram bot वाला पूरा कोड रहेगा)


# =========================================================
# आपका Telegram Bot वाला पिछला कोड यहाँ नीचे रहेगा
# =========================================================

import os
import threading
from flask import Flask

# 1. Web Server for App & UptimeRobot
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Forex AI Bot</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0f172a; color: white; text-align: center; padding: 20px; }
            .card { background: #1e293b; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #334155; }
            .status { color: #22c55e; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>🤖 Forex AI Bot Dashboard</h1>
        <div class="card">
            <h3>⚡ System Status</h3>
            <p class="status">● Running Live 24/7</p>
            <p>Telegram Signals & Auto Trader: ACTIVE</p>
        </div>
    </body>
    </html>
    """

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Background में Web Server चालू करें
threading.Thread(target=run_web_server).start()

# ---------------------------------------------------------
# 2. इसके नीचे आपका पुराना main.py का Telegram Bot वाला Code रहेगा
# ---------------------------------------------------------

import os
import threading
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import requests
import ta
import yfinance as yf
from flask import Flask
from sklearn.ensemble import RandomForestClassifier

app = Flask(__name__)


@app.route("/")
def home():
    return "Multi-Pair AI Forex Super Bot is Running Live 24/7!"


TELEGRAM_BOT_TOKEN = "8767606359:AAH7dZn_9dsT1HwmOkbvKAB2bgB2aEvOz0c"
TELEGRAM_CHAT_ID = "6449682719"


def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Error: Telegram credentials missing!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("📲 Telegram Alert Successfully Sent!")
        else:
            print(f"❌ Failed to send: {response.text}")
    except Exception as e:
        print(f"❌ Error sending alert: {e}")


def is_high_impact_news_coming():
    """Checks for High-Impact USD/EUR News to avoid trading during volatility."""
    try:
        url = "https://nws.s3.amazonaws.com/nws-s3-prod/cal.json"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            events = response.json()
            now = datetime.now(timezone.utc)
            for event in events:
                if event.get("impact") == "High" and event.get(
                    "currency"
                ) in ["USD", "EUR", "GBP"]:
                    event_time = datetime.fromisoformat(
                        event["date"].replace("Z", "+00:00")
                    )
                    time_diff = (event_time - now).total_seconds() / 60
                    if -15 <= time_diff <= 45:
                        return True, event.get("title")
    except Exception as e:
        print(f"⚠️ News fetch skipped/error: {e}")
    return False, None


def analyze_symbol(symbol, name):
    """Fetches data and runs AI prediction for a specific asset."""
    try:
        data = yf.download(
            symbol, period="1mo", interval="1h", auto_adjust=True
        )
        if data.empty:
            return f"❌ {name}: Data fetch failed!"

        if isinstance(data.columns, pd.MultiIndex):
            df = pd.DataFrame(
                {
                    "Close": data["Close"][symbol],
                    "High": data["High"][symbol],
                    "Low": data["Low"][symbol],
                }
            ).dropna()
        else:
            df = data[["Close", "High", "Low"]].dropna()

        # Indicators
        df["SMA_10"] = ta.trend.sma_indicator(df["Close"], window=10)
        df["SMA_30"] = ta.trend.sma_indicator(df["Close"], window=30)
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
        df["MACD"] = ta.trend.macd_diff(df["Close"])

        bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
        df["BB_High"] = bb.bollinger_hband()
        df["BB_Low"] = bb.bollinger_lband()
        df["ATR"] = ta.volatility.average_true_range(
            df["High"], df["Low"], df["Close"], window=14
        )

        df["Price_Change"] = df["Close"].pct_change()
        df["Target"] = np.where(df["Close"].shift(-1) > df["Close"], 1, 0)
        df = df.dropna()

        features = [
            "SMA_10",
            "SMA_30",
            "RSI",
            "MACD",
            "BB_High",
            "BB_Low",
            "ATR",
            "Price_Change",
        ]
        X = df[features]
        y = df["Target"]

        model = RandomForestClassifier(n_estimators=200, random_state=42)
        model.fit(X, y)

        latest_features = X.iloc[[-1]]
        latest_price = float(df["Close"].iloc[-1])
        latest_atr = float(df["ATR"].iloc[-1])
        prediction = model.predict(latest_features)[0]

        sl_pip = latest_atr * 1.5
        tp_pip = latest_atr * 3.0

        if prediction == 1:
            sl_price = latest_price - sl_pip
            tp_price = latest_price + tp_pip
            return (
                f"🚀 *{name} SIGNAL: BUY* 🚀\n"
                f"• *Entry:* {latest_price:.5f}\n"
                f"• *SL:* {sl_price:.5f} | *TP:* {tp_price:.5f}\n"
                f"• *Risk/Reward:* 1:2\n"
            )
        else:
            return f"🔴 *{name}: NO BUY / HOLD* (Price: {latest_price:.5f})\n"

    except Exception as e:
        return f"❌ {name} Error: {e}"


def run_super_bot_logic():
    print("🔄 Running Multi-Pair Market Analysis...")

    has_news, news_title = is_high_impact_news_coming()
    if has_news:
        msg = f"⚠️ *HIGH IMPACT NEWS ALERT* ⚠️\n\n*Event:* {news_title}\n*Action:* Market is volatile. Pausing automated signals for 1 hour!"
        send_telegram_alert(msg)
        return

    pairs = [
        ("EURUSD=X", "EUR/USD"),
        ("GC=F", "GOLD (XAU/USD)"),
        ("GBPUSD=X", "GBP/USD"),
    ]

    full_report = "🤖 *AI MULTI-PAIR FOREX REPORT* 🤖\n\n"
    for symbol, name in pairs:
        result = analyze_symbol(symbol, name)
        full_report += result + "\n"

    full_report += "⏳ Next update in 1 hour."
    print(full_report)
    send_telegram_alert(full_report)


def bot_loop():
    run_super_bot_logic()
    while True:
        time.sleep(3600)


bot_thread = threading.Thread(target=bot_loop, daemon=True)
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

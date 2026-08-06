
Raw file content
Copilot
View options
Skip to content
pd7691033798-ai
forex-ai-bot
Repository navigation
Code
Issues
Pull requests
Agents
Actions
Projects
Wiki
Security and quality
1
 (1)
Insights
Settings
forex-ai-bot
/main.py
Go to file
t
T
pd7691033798-ai
pd7691033798-ai
Rename main py to main.py
10589d1
 · 
16 minutes ago

Code

Blame
98 lines (79 loc) · 3.09 KB
import os
import threading
import time
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
    return "Forex Trading Bot is Running Live 24/7!"

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
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("📲 Telegram Alert Successfully Sent!")
        else:
            print(f"❌ Failed to send: {response.text}")
    except Exception as e:
        print(f"❌ Error sending alert: {e}")

def run_bot_logic():
    print("🔄 Fetching Market Data...")
    try:
        data = yf.download("EURUSD=X", period="1mo", interval="1h", auto_adjust=True)

        if data.empty:
            print("❌ Data fetch failed!")
            return

        if isinstance(data.columns, pd.MultiIndex):
            close_price = data["Close"]["EURUSD=X"]
        else:
            close_price = data["Close"]

        df = pd.DataFrame({"Close": close_price}).dropna()

        df["SMA_10"] = ta.trend.sma_indicator(df["Close"], window=10)
        df["SMA_30"] = ta.trend.sma_indicator(df["Close"], window=30)
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
        df["MACD"] = ta.trend.macd_diff(df["Close"])
        df["Price_Change"] = df["Close"].pct_change()
        df["Target"] = np.where(df["Close"].shift(-1) > df["Close"], 1, 0)
        df = df.dropna()

        features = ["SMA_10", "SMA_30", "RSI", "MACD", "Price_Change"]
        X = df[features]
        y = df["Target"]

        model = RandomForestClassifier(n_estimators=200, random_state=42)
        model.fit(X, y)

        latest_features = X.iloc[[-1]]
        latest_price = float(df["Close"].iloc[-1])
        prediction = model.predict(latest_features)[0]

        if prediction == 1:
            signal_msg = f"🟢 *AI BOT FOREX SIGNAL: BUY* 🟢\n\n*Pair:* EUR/USD\n*Price:* {latest_price:.5f}\n*Action:* Buy Order\n*SL:* 0.3% | *TP:* 0.6%"
        else:
            signal_msg = f"🔴 *AI BOT FOREX SIGNAL: SELL / HOLD* 🔴\n\n*Pair:* EUR/USD\n*Price:* {latest_price:.5f}\n*Action:* No Buy Signal"

        print("Latest Signal:\n", signal_msg)
        send_telegram_alert(signal_msg)

    except Exception as e:
        print(f"❌ Error in bot loop: {e}")

def bot_loop():
    run_bot_logic()
    while True:
        print("⏳ Waiting 1 hour for next analysis...")
        time.sleep(3600)

bot_thread = threading.Thread(target=bot_loop, daemon=True)
bot_thread.start()

if __name__ == "__main.py__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
 

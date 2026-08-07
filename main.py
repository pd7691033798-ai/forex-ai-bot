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

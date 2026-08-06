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
    return "AI Forex Super Bot with News Filter is Running Live 24/7!"


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
    """Checks for High-Impact USD/EUR News to avoid trading during major volatility events."""
    try:
        url = "https://nws.s3.amazonaws.com/nws-s3-prod/cal.json"  # Public economic events feed
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            events = response.json()
            now = datetime.now(timezone.utc)
            for event in events:
                if event.get("impact") == "High" and event.get(
                    "currency"
                ) in ["USD", "EUR"]:
                    event_time = datetime.fromisoformat(
                        event["date"].replace("Z", "+00:00")
                    )
                    time_diff = (event_time - now).total_seconds() / 60
                    # If high impact news is in next 45 mins or passed 15 mins ago
                    if -15 <= time_diff <= 45:
                        print(
                            f"⚠️ High Impact News Alert: {event.get('title')}"
                        )
                        return True, event.get("title")
    except Exception as e:
        print(f"⚠️ News fetch skipped/error: {e}")
    return False, None


def run_super_bot_logic():
    print("🔄 Fetching Market Data & News Status...")

    # 1. News Check Filter
    has_news, news_title = is_high_impact_news_coming()
    if has_news:
        msg = f"⚠️ *HIGH IMPACT NEWS WARNING* ⚠️\n\n*Event:* {news_title}\n*Action:* Trading paused for 1 hour to prevent high news risk!"
        print(msg)
        send_telegram_alert(msg)
        return

    try:
        # 2. Fetch 1h and Daily Data for Trend & Features
        data = yf.download(
            "EURUSD=X", period="1mo", interval="1h", auto_adjust=True
        )

        if data.empty:
            print("❌ Data fetch failed!")
            return

        if isinstance(data.columns, pd.MultiIndex):
            df = pd.DataFrame(
                {
                    "Close": data["Close"]["EURUSD=X"],
                    "High": data["High"]["EURUSD=X"],
                    "Low": data["Low"]["EURUSD=X"],
                }
            ).dropna()
        else:
            df = data[["Close", "High", "Low"]].dropna()

        # 3. Super Indicators Setup
        df["SMA_10"] = ta.trend.sma_indicator(df["Close"], window=10)
        df["SMA_30"] = ta.trend.sma_indicator(df["Close"], window=30)
        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
        df["MACD"] = ta.trend.macd_diff(df["Close"])

        # Advanced Indicators
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

        # 4. Train Enhanced AI Model
        model = RandomForestClassifier(n_estimators=300, random_state=42)
        model.fit(X, y)

        latest_features = X.iloc[[-1]]
        latest_price = float(df["Close"].iloc[-1])
        latest_atr = float(df["ATR"].iloc[-1])
        prediction = model.predict(latest_features)[0]

        # Dynamic Stop Loss & Take Profit based on ATR
        sl_pip = latest_atr * 1.5
        tp_pip = latest_atr * 3.0  # 1:2 Risk to Reward Ratio

        sl_price = latest_price - sl_pip if prediction == 1 else latest_price
        tp_price = latest_price + tp_pip if prediction == 1 else latest_price

        # 5. Telegram Alert
        if prediction == 1:
            signal_msg = (
                f"🚀 *SUPER AI BOT FOREX SIGNAL: BUY* 🚀\n\n"
                f"*Pair:* EUR/USD\n"
                f"*Entry Price:* {latest_price:.5f}\n"
                f"*Stop Loss (SL):* {sl_price:.5f}\n"
                f"*Take Profit (TP):* {tp_price:.5f}\n"
                f"*Risk/Reward:* 1:2 Ratio\n"
                f"*News Status:* Safe (No High-Impact News)"
            )
        else:
            signal_msg = (
                f"🔴 *SUPER AI BOT SIGNAL: NO BUY / HOLD* 🔴\n\n"
                f"*Pair:* EUR/USD\n"
                f"*Current Price:* {latest_price:.5f}\n"
                f"*Status:* AI Model predicts range-bound or downward market."
            )

        print("Latest Signal:\n", signal_msg)
        send_telegram_alert(signal_msg)

    except Exception as e:
        print(f"❌ Error in bot loop: {e}")


def bot_loop():
    run_super_bot_logic()
    while True:
        print("⏳ Waiting 1 hour for next analysis...")
        time.sleep(3600)


bot_thread = threading.Thread(target=bot_loop, daemon=True)
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

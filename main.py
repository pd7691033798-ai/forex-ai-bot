import os
import threading
import json
import time
import requests
import websocket
from flask import Flask, request, jsonify

app = Flask(__name__)

DERIV_API_TOKEN = "YOUR_DERIV_API_TOKEN_HERE"  # 👈 अपना Deriv API Token यहाँ सही से डालें
APP_ID = "pat_504c2a11cdff0965d23fa7cdcc496f8ab42756562baeaca3d5a04490b29ea9a3"

def send_deriv_trade(symbol, trade_type, amount=10):
    print(f"👉 EXECUTION TRIGGERED FOR: {symbol} | {trade_type}", flush=True)

    def on_open(ws):
        print("🔗 WebSocket Connected! Authorizing Token...", flush=True)
        ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))

    def on_message(ws, message):
        data = json.loads(message)
        print(f"📩 Deriv Response: {data}", flush=True)

        if data.get("msg_type") == "authorize":
            if "error" in data:
                print(f"❌ AUTH ERROR: {data['error']['message']}", flush=True)
                ws.close()
            else:
                print("✅ Token Authorized! Sending Order Proposal...", flush=True)
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
            else:
                print(f"🚀 SUCCESS! Trade Placed. ID: {data['buy']['transaction_id']}", flush=True)
            ws.close()

    def on_error(ws, error):
        print(f"⚠️ WS ERROR: {error}", flush=True)

    ws_url = f"wss://ws.derivws.com/websockets/v3?app_id={APP_ID}"
    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open, 
        on_message=on_message,
        on_error=on_error
    )
    ws.run_forever()

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Deriv AI Auto-Trader</title>
        <style>
            body { background: #0d1117; color: white; text-align: center; font-family: sans-serif; padding: 15px; }
            .card { background: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
            .btn { width: 45%; padding: 15px; margin: 5px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; color: white; }
            .btn-buy { background: #238636; }
            .btn-sell { background: #da3633; }
        </style>
    </head>
    <body>
        <h2>🤖 Deriv 100% Cloud Auto-Trader</h2>
        <div class="card">
            <h4>Select Market</h4>
            <select id="symbolSelect" style="padding: 10px; width: 80%; background: #21262d; color: white; border-radius: 5px;">
                <option value="XAUUSD">GOLD (XAU/USD)</option>
                <option value="EURUSD">EUR/USD</option>
            </select>
        </div>
        
        <div class="card">
            <h4>Quick Trade Execution</h4>
            <button class="btn btn-buy" onclick="triggerTrade('BUY')">BUY 📈</button>
            <button class="btn btn-sell" onclick="triggerTrade('SELL')">SELL 📉</button>
        </div>

        <script>
            function triggerTrade(action) {
                let symbol = document.getElementById('symbolSelect').value;
                alert("Sending " + action + " order for " + symbol + " to Deriv Cloud Server...");
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
    return jsonify({"status": "Trade Execution Request Sent"})

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    run_web_server()

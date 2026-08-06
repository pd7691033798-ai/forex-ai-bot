import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>My Forex AI Trading Bot</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a; color: #f8fafc; text-align: center; padding: 20px; margin: 0; }
            .container { max-width: 450px; margin: 0 auto; }
            .card { background: #1e293b; padding: 20px; margin: 15px 0; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); border: 1px solid #334155; }
            .status { color: #38bdf8; font-weight: bold; font-size: 1.1em; }
            .badge { background: #22c55e; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9em; }
            .buy { color: #4ade80; font-weight: bold; }
            .hold { color: #fbbf24; font-weight: bold; }
            h1 { font-size: 1.6em; color: #f1f5f9; margin-bottom: 5px; }
            p { margin: 8px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 My Forex AI Bot</h1>
            <p style="color: #94a3b8; font-size: 0.9em;">Automated Trading Control Center</p>
            
            <div class="card">
                <h3>⚡ Bot Status</h3>
                <p><span class="badge">ONLINE 24/7</span></p>
                <p class="status" style="margin-top: 10px;">Uptime Monitoring: Active 🟢</p>
            </div>

            <div class="card">
                <h3>📊 Live Market Signals</h3>
                <hr style="border-color: #334155; margin: 15px 0;">
                <p>GOLD (XAU/USD): <span class="buy">BUY 📈</span></p>
                <p>EUR/USD: <span class="hold">HOLD ⏸️</span></p>
                <p>GBP/USD: <span class="hold">HOLD ⏸️</span></p>
            </div>

            <p style="color: #64748b; font-size: 0.8em; margin-top: 25px;">App Version 1.0 • Connected to Render Cloud</p>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

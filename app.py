from flask import Flask, request, jsonify
from dhanhq import dhanhq
import os
import math
from datetime import datetime

app = Flask(__name__)

# ======================
# DHAN CONFIG (ENV VARS)
# ======================
CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

dhan = dhanhq(
    client_id=CLIENT_ID,
    access_token=ACCESS_TOKEN
)

# ======================
# GLOBAL STATE
# ======================
last_price = None
trade_lock = False
current_position = None


def get_atm_strike(price):
    return round(price / 50) * 50


# ======================
# HEALTH CHECK
# ======================
@app.route("/")
def home():
    return "NIFTY Automation Server Running"


# ======================
# TRADINGVIEW WEBHOOK
# ======================
@app.route("/webhook", methods=["POST"])
def webhook():
    global last_price, trade_lock, current_position

    data = request.json
    message = data.get("message", "").upper()

    if "ZIGZAG" not in message:
        return jsonify({"status": "ignored"})

    if trade_lock:
        return jsonify({"status": "trade locked"})

    ltp = dhan.get_ltp("NSE", "NIFTY")["data"]["ltp"]

    if last_price is None:
        last_price = ltp
        return jsonify({"status": "first price stored"})

    direction = "CE" if ltp > last_price else "PE"
    strike = get_atm_strike(ltp)

    option_symbol = f"NIFTY {strike} {direction}"

    dhan.place_order(
        exchange="NFO",
        symbol=option_symbol,
        transaction_type="BUY",
        quantity=50,
        product_type="MIS",
        order_type="MARKET",
        price=0
    )

    trade_lock = True
    current_position = option_symbol
    last_price = ltp

    return jsonify({
        "status": "order placed",
        "symbol": option_symbol
    })


# ======================
# DHAN POSTBACK
# ======================
@app.route("/postback", methods=["POST"])
def postback():
    global trade_lock, current_position

    data = request.json
    status = data.get("status")

    if status in ["COMPLETE", "REJECTED", "CANCELLED"]:
        # You can refine this later
        print("Postback:", data)

    # Example: reset lock after exit
    if status == "COMPLETE" and data.get("transaction_type") == "SELL":
        trade_lock = False
        current_position = None

    return jsonify({"status": "ok"})


# ======================
# RUN SERVER
# ======================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

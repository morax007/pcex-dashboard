from flask import Flask, request, render_template, redirect, jsonify
import sqlite3
from datetime import datetime, timedelta
from telegram import Bot


app = Flask(__name__)

BOT_TOKEN = "7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg"

DB_PATH = "users.db"

SUBSCRIPTION_PLANS = {
    "Basic": {"price": "5 USDT", "duration_days": 7},
    "Pro": {"price": "12 USDT", "duration_days": 30},
    "Premium": {"price": "30 USDT", "duration_days": 90},
}

# --- DB Utilities ---
def get_user(tg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
    user = c.fetchone()
    conn.close()
    return user

def update_user_connection(tg_id, username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE users 
        SET pcex_username = ?, pcex_password = ?, is_connected = 1
        WHERE telegram_id = ?
    """, (username, password, tg_id))
    conn.commit()
    conn.close()

# --- Routes ---
@app.route("/")
def home():
    return "✅ Dashboard is running."

@app.route("/connect")
def connect():
    tg_id = request.args.get("tg_id")
    token = request.args.get("auth_token")
    print("🔍 Received tg_id:", tg_id)
    print("🔍 Received token:", token)
    
    user = get_user(tg_id)
    print("🔍 DB record for user:", user)

    if not user or user[1] != token:
        return "❌ Invalid token or session", 403

    return render_template("pcex_login.html", tg_id=tg_id, token=token)

@app.route("/submit_login", methods=["POST"])
def submit_login():
    tg_id = request.form.get("tg_id")
    token = request.form.get("token")
    username = request.form.get("username")
    password = request.form.get("password")

    user = get_user(tg_id)
    if not user or user[1] != token:
        return "❌ Invalid session.", 403

    update_user_connection(tg_id, username, password)
    return "✅ PCEX credentials saved. You can now return to Telegram."

@app.route("/nowpayments/webhook", methods=["POST"])
def nowpayments_webhook():
    data = request.json
    print("🧾 Webhook received:", data)
    payment_status = data.get("payment_status")
    order_id = data.get("order_id")

    if payment_status != "finished" or not order_id:
        return jsonify({"status": "ignored"}), 200

    try:
        tg_id, plan, _ = order_id.split("_")
    except ValueError:
        return jsonify({"error": "Invalid order_id format"}), 400

    if plan not in SUBSCRIPTION_PLANS:
        return jsonify({"error": "Invalid plan"}), 400

    duration_days = SUBSCRIPTION_PLANS[plan]["duration_days"]
    expiry_date = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE users
            SET is_subscribed = 1,
                plan = ?,
                subscription_expiry = ?
            WHERE telegram_id = ?
        """, (plan, expiry_date, tg_id))
        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ✅ Send Telegram notification
    try:
        BOT_TOKEN = "7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg"
        bot = Bot(token=BOT_TOKEN)
        bot.send_message(
            chat_id=int(tg_id),
            text=f"🎉 Payment confirmed! Your *{plan}* subscription is now active.",
            parse_mode="Markdown"
        )
        print(f"📤 Notification sent to Telegram user {tg_id}")
    except Exception as e:
        print(f"❌ Failed to send Telegram message: {e}")

    return jsonify({"status": "updated"}), 200

if __name__ == "__main__":
 
    app.run(host="0.0.0.0", port=3000)
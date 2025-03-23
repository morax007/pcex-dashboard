import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
import pytz
import urllib.parse
import httpx
import os

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import init_db, create_or_update_user, set_trial_start, get_user

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants ---
WEB_DASHBOARD_URL = "http://127.0.0.1:5000/connect"
BOT_TOKEN = "7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg"
ADMIN_TELEGRAM_ID = "8195940821"  # Replace with your actual Telegram user ID
NOWPAYMENTS_API_KEY = "ZFBBWG4-43847WG-NHV8WKA-XZB06QQ"  # Replace with your real API key

SUBSCRIPTION_PLANS = {
    "Basic": {"price": "5 USDT", "duration_days": 7},
    "Pro": {"price": "12 USDT", "duration_days": 30},
    "Premium": {"price": "30 USDT", "duration_days": 90},
}

# --- Bot Handlers ---
async def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    logger.info(f"👤 Telegram ID: {user_id}")

    token = create_or_update_user(user_id)
    set_trial_start(user_id)

    encoded_token = urllib.parse.quote(token)
    link = f"{WEB_DASHBOARD_URL}?tg_id={user_id}&auth_token={encoded_token}"

    keyboard = [[InlineKeyboardButton("🔗 Connect to Dashboard", url=link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome! Click below to securely connect to the web dashboard and start your 3-day free trial:",
        reply_markup=reply_markup
    )

async def status(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("No user record found. Use /start to begin.")
        return

    is_connected = bool(user[2])
    trial_start = user[4]
    is_subscribed = int(user[5]) == 1
    plan = user[6] if user[6] else "N/A"
    subscription_expiry = user[7]

    msg = f"\nConnected: {'✅' if is_connected else '❌'}"

    if is_subscribed:
        if subscription_expiry:
            expiry = datetime.fromisoformat(subscription_expiry)
            days_left = (expiry - datetime.utcnow()).days
            if days_left >= 0:
                msg += f"\nSubscription: ✅ Plan - {plan} ({days_left + 1} day(s) left)"
            else:
                msg += f"\nSubscription: ❌ Expired Plan - {plan}"
        else:
            msg += f"\nSubscription: ✅ Plan - {plan}"
    else:
        if trial_start:
            days_used = (datetime.utcnow() - datetime.fromisoformat(trial_start)).days
            days_left = 2 - days_used
            if days_left >= 0:
                msg += f"\nTrial: ⏳ {days_left + 1} day(s) remaining"
            else:
                msg += "\nTrial: ❌ Expired"
        else:
            msg += "\nTrial: ❌ Not started"

    await update.message.reply_text(msg)

async def subscribe(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton(f"🟢 Basic - 5 USDT (7 days)", callback_data="sub_Basic")],
        [InlineKeyboardButton(f"🔵 Pro - 12 USDT (30 days)", callback_data="sub_Pro")],
        [InlineKeyboardButton(f"🟣 Premium - 30 USDT (90 days)", callback_data="sub_Premium")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📦 Choose a subscription plan:",
        reply_markup=reply_markup
    )

async def handle_subscription_choice(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    choice = query.data.replace("sub_", "")
    plan = SUBSCRIPTION_PLANS.get(choice)

    if not plan:
        await query.edit_message_text("❌ Invalid plan selection.")
        return

    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }

    invoice_payload = {
        "price_amount": float(plan["price"].split()[0]),
        "price_currency": "usdtbsc",
        "pay_currency": "usdtbsc",
        "order_id": f"{user_id}_{choice}_{datetime.utcnow().timestamp()}",
        "order_description": f"Telegram user {user_id} chose {choice} plan",
        "ipn_callback_url": "https://yourdomain.com/nowpayments/webhook",
        "success_url": "https://t.me/YourBotUsername",
        "cancel_url": "https://t.me/YourBotUsername"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post("https://api.nowpayments.io/v1/invoice", json=invoice_payload, headers=headers)

    if response.status_code == 200:
        invoice = response.json()
        await query.edit_message_text(
            f"💳 Plan: {choice}\n💰 Amount: {plan['price']}\n\n"
            f"Click below to pay:\n{invoice['invoice_url']}",
            disable_web_page_preview=False
        )
    else:
        await query.edit_message_text("❌ Failed to generate payment. Please try again later.")

async def confirm_payment(update: Update, context: CallbackContext):
    admin_id = str(update.effective_user.id)
    logger.info(f"[ADMIN CHECK] Command from: {admin_id}")

    if admin_id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text("❌ You are not authorized to run this command.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /confirm_payment <telegram_id> <plan>")
        return

    tg_id, plan_name = context.args
    logger.info(f"[CONFIRM PAYMENT] tg_id={tg_id}, plan={plan_name}")

    plan = SUBSCRIPTION_PLANS.get(plan_name)
    if not plan:
        await update.message.reply_text("❌ Invalid plan name.")
        return

    duration_days = plan["duration_days"]
    expiry_date = (datetime.utcnow() + timedelta(days=duration_days)).isoformat()

    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("""
            UPDATE users
            SET is_subscribed = 1,
                plan = ?,
                subscription_expiry = ?
            WHERE telegram_id = ?
        """, (plan_name, expiry_date, tg_id))
        conn.commit()
        conn.close()
        logger.info(f"[DB UPDATE] User {tg_id} set to subscribed ({plan_name})")
    except Exception as e:
        logger.error(f"[DB ERROR] Failed to update DB: {e}")

    await update.message.reply_text(f"✅ Subscription for user {tg_id} activated with plan: {plan_name}")

    try:
        await context.bot.send_message(
            chat_id=int(tg_id),
            text=f"🎉 Your subscription ({plan_name}) has been activated. Thank you!"
        )
    except Exception as e:
        logger.warning(f"Could not notify user {tg_id}: {e}")

async def renew(update: Update, context: CallbackContext):
    await subscribe(update, context)

# --- Main ---
async def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("renew", renew))
    app.add_handler(CommandHandler("confirm_payment", confirm_payment))
    app.add_handler(CallbackQueryHandler(handle_subscription_choice, pattern=r"^sub_"))

    logger.info("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())

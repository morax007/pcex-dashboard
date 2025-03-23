# bot.py
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackContext
from db import init_db, create_or_update_user

WEB_DASHBOARD_URL = "https://yourdashboard.com/connect"
BOT_TOKEN = "7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg"

async def start(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    token = create_or_update_user(user_id)

    link = f"{WEB_DASHBOARD_URL}?tg_id={user_id}&auth_token={token}"

    keyboard = [[InlineKeyboardButton("🔗 Connect to Dashboard", url=link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome! Click below to securely connect to the web dashboard 👇",
        reply_markup=reply_markup
    )

async def status(update: Update, context: CallbackContext):
    from db import get_user
    user = get_user(str(update.effective_user.id))
    if user:
        status = "✅ Connected" if user[2] == 1 else "❌ Not connected"
        await update.message.reply_text(f"Your status: {status}")
    else:
        await update.message.reply_text("You haven't started the setup yet. Use /start.")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))

    app.run_polling()

if __name__ == "__main__":
    main()

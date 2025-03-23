import re
import logging
import asyncio
from datetime import datetime, timedelta
import pytz

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Fix for event loop in interactive environments
import nest_asyncio
nest_asyncio.apply()

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
LOGIN_USERNAME, LOGIN_PASSWORD = range(2)

# Global sessions: {user_id: {'username': ..., 'password': ..., 'last_active': datetime}}
sessions = {}

# Chat and bot config
TOKEN = "YOUR_BOT_TOKEN"  # <-- Replace this with your bot token
GROUP_CHAT_ID = -2229105804  # <-- Replace this with your Telegram group ID

PCEX_LOGIN_URL = "https://pcex.com/pc/#/login"
SESSION_TIMEOUT = timedelta(minutes=10)
CODE_REGEX = re.compile(r"\b[a-zA-Z0-9]{7,10}\b")

# ---------- Selenium Automation ----------
def automation_run(username: str, password: str, code: str) -> bool:
    try:
        driver = webdriver.Chrome()
        wait = WebDriverWait(driver, 20)

        driver.get(PCEX_LOGIN_URL)

        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username_field.clear()
        username_field.send_keys(username)

        password_field = wait.until(EC.presence_of_element_located((By.ID, "password")))
        password_field.clear()
        password_field.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
        login_button.click()

        # Wait for homepage
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'homepage')]")))

        futures_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Futures')]")))
        futures_tab.click()

        invited_me_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Invited Me')]")))
        invited_me_tab.click()

        code_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='please enter the code']")))
        code_field.clear()
        code_field.send_keys(code)

        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Submit')]")))
        submit_button.click()

        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(),'Success')]")))
        driver.quit()
        return True

    except Exception as e:
        logger.error("Automation failed: %s", e)
        try:
            driver.quit()
        except:
            pass
        return False

# ---------- Telegram Handlers ----------
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Welcome! Use /login to enter your PCEX credentials.")

async def login_start(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Enter your PCEX username:")
    return LOGIN_USERNAME

async def login_username(update: Update, context: CallbackContext) -> int:
    context.user_data["pcex_username"] = update.message.text.strip()
    await update.message.reply_text("Enter your PCEX password:")
    return LOGIN_PASSWORD

async def login_password(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    sessions[user_id] = {
        "username": context.user_data.get("pcex_username"),
        "password": update.message.text.strip(),
        "last_active": datetime.now()
    }
    await update.message.reply_text("Credentials saved. You will be auto-logged out after 10 minutes of inactivity.")
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Login cancelled.")
    return ConversationHandler.END

async def status(update: Update, context: CallbackContext):
    session = sessions.get(update.effective_user.id)
    if session and datetime.now() - session["last_active"] < SESSION_TIMEOUT:
        await update.message.reply_text("✅ Your session is active.")
    else:
        await update.message.reply_text("❌ Session expired or not found. Use /login again.")

# ---------- Scheduled Task ----------
async def scheduled_task(app: Application):
    logger.info("Running scheduled task...")

    try:
        chat = await app.bot.get_chat(GROUP_CHAT_ID)
        pinned = chat.pinned_message
    except Exception as e:
        logger.error("Error getting group chat or pinned message: %s", e)
        return

    if not pinned or not pinned.text:
        logger.info("No pinned message found.")
        return

    match = CODE_REGEX.search(pinned.text)
    if not match:
        logger.info("No code found in pinned message.")
        return

    code = match.group(0)
    logger.info("Code extracted: %s", code)

    for user_id, session in list(sessions.items()):
        if datetime.now() - session["last_active"] > SESSION_TIMEOUT:
            try:
                await app.bot.send_message(chat_id=user_id, text="⏳ Session expired. Please /login again.")
            except:
                pass
            sessions.pop(user_id)
            continue

        username = session["username"]
        password = session["password"]
        success = await asyncio.to_thread(automation_run, username, password, code)

        msg = f"✅ PCEX update successful with code: {code}" if success else f"❌ Failed to update PCEX with code: {code}"
        try:
            await app.bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logger.error("Failed to send update to user %s: %s", user_id, e)

        session["last_active"] = datetime.now()

# ---------- Main App ----------
async def main():
    app = Application.builder().token("7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            LOGIN_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("status", status))

    scheduler = AsyncIOScheduler(timezone=pytz.timezone("America/Los_Angeles"))
    for hour in [4, 5, 8, 9]:
        scheduler.add_job(scheduled_task, "cron", args=[app], hour=hour, minute=0)
    scheduler.start()

    logger.info("Bot is running...")
    await app.run_polling()

# ---------- Entry ----------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, CallbackContext

TOKEN = "7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg"

async def start(update: Update, context: CallbackContext):
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text("Hello! I'm an echo bot. Send me a message, and I'll repeat it!")

async def echo(update: Update, context: CallbackContext):
    """Echo the user message."""
    await update.message.reply_text(update.message.text)

async def main():
    """Main function to run the bot."""
    app = Application.builder().token(TOKEN).build()

    # Add command and message handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("Bot is running...")
    await app.run_polling()

# Apply nest_asyncio to fix event loop issues in interactive environments
nest_asyncio.apply()

# Run the event loop manually
loop = asyncio.get_event_loop()
loop.run_until_complete(main())

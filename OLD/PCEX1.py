import telegram
from telegram.ext import Updater, MessageHandler, filters, CommandHandler

# Replace 'YOUR_TOKEN' with your actual bot token
TOKEN = '7708362431:AAHquLb5XaCecJzGZjnXA1xS_m19-Adwykg'

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Hello! I'm an echo bot. Send me a message, and I'll repeat it!")

def echo(update, context):
    text = update.message.text
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def main():
    updater = Updater(TOKEN, use_context=True) # use_context=True is very important.
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
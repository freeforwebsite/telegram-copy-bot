from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

import os

def load_env():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    os.environ[key] = val
    except FileNotFoundError:
        pass

load_env()
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

DESTINATION_CHANNEL_ID = ""

async def copy_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copies any received message and sends it to the destination."""
    if not update.message:
        return
        
    chat_id_to_send = DESTINATION_CHANNEL_ID if DESTINATION_CHANNEL_ID else update.effective_chat.id
    
    try:
        await context.bot.copy_message(
            chat_id=chat_id_to_send,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        print("Message successfully copied!")
    except Exception as e:
        print(f"Failed to copy message: {e}")

def main():
    print("Starting bot...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, copy_message_handler))
    print("Bot is online! Send a file to the bot.")
    application.run_polling()

import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == '__main__':
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    main()

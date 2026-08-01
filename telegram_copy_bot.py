from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

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

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a grand welcome message when the command /start is issued."""
    welcome_text = (
        "✨ *Welcome to the Ultimate Copy Bot\\!* ✨\n\n"
        "I am your personal assistant designed to instantly clone messages, files, and media *without the annoying 'Forwarded from' tag*\\.\n\n"
        "📜 *How to use me:*\n"
        "1️⃣ Simply forward or send any file, photo, or message to me\\.\n"
        "2️⃣ I will immediately process it and send you back a crystal\\-clean copy\\.\n"
        "3️⃣ You can then share this clean copy anywhere you like\\!\n\n"
        "⚡ _Fast, secure, and completely untraceable\\._\n\n"
        "Drop a file below to see the magic\\! 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="MarkdownV2")

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

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

def main():
    print("Starting dummy web server for Render...")
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    print("Starting bot...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start_handler))
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

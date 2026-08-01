from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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

# Dictionary to store where each user is currently sending their files
user_destinations = {}

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a grand welcome message when the command /start is issued."""
    welcome_text = (
        "✨ *Welcome to the Ultimate Multi-Channel Copy Bot\\!* ✨\n\n"
        "I am your personal assistant designed to instantly clone files to ANY of your channels *without the 'Forwarded from' tag*\\.\n\n"
        "📜 *How to use me:*\n"
        "1️⃣ Use `/set @yourchannel` to tell me which channel to post to\\.\n"
        "2️⃣ Send me as many files as you want\\. I will instantly post them all to that channel perfectly clean\\!\n"
        "3️⃣ When you want to switch to a different channel, just use `/set @anotherchannel`\\.\n"
        "4️⃣ Use `/clear` if you want me to just send files back to you privately\\.\n\n"
        "⚡ _Make sure I am added as an Admin to your channels so I can post\\!_"
    )
    await update.message.reply_text(welcome_text, parse_mode="MarkdownV2")

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets the destination channel for the user."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a channel username or ID.\n\nExample: `/set @strangerthings_channel` or `/set -100123456789`", parse_mode="Markdown")
        return
    
    channel = context.args[0]
    user_id = update.effective_user.id
    user_destinations[user_id] = channel
    
    await update.message.reply_text(f"✅ **Target Channel Locked!**\n\nDestination set to: {channel}\n\nAny files you send me right now will be automatically posted straight into that channel. (Please ensure I am an admin there!)", parse_mode="Markdown")

async def clear_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears the destination channel."""
    user_id = update.effective_user.id
    if user_id in user_destinations:
        del user_destinations[user_id]
    await update.message.reply_text("🛑 Target cleared! Any files you send will now just be returned to you privately here.")

async def copy_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copies any received message and sends it to the destination."""
    if not update.message:
        return
        
    user_id = update.effective_user.id
    
    # If the user has a destination set, send it there. Otherwise, send it back to them privately.
    chat_id_to_send = user_destinations.get(user_id, update.effective_chat.id)
    
    try:
        await context.bot.copy_message(
            chat_id=chat_id_to_send,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id
        )
        
        # If we successfully sent it to a channel, optionally let the user know (uncomment next line if you want confirmation)
        # if chat_id_to_send != update.effective_chat.id:
        #    await update.message.reply_text("✅ Sent to channel!")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send to channel. Are you sure I am an admin in `{chat_id_to_send}`?\n\nError details: {e}", parse_mode="Markdown")


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
    application.add_handler(CommandHandler('set', set_destination))
    application.add_handler(CommandHandler('clear', clear_destination))
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

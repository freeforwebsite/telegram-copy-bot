from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

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

# State
user_destinations = {}
user_saved_channels = {} # user_id -> list of channel strings

def save_state():
    try:
        with open('bot_state.json', 'w') as f:
            json.dump({'dest': user_destinations, 'saved': user_saved_channels}, f)
    except Exception:
        pass

def load_state():
    global user_destinations, user_saved_channels
    try:
        with open('bot_state.json', 'r') as f:
            data = json.load(f)
            # JSON keys are strings, convert back to int for user_ids
            user_destinations = {int(k): v for k, v in data.get('dest', {}).items()}
            user_saved_channels = {int(k): v for k, v in data.get('saved', {}).items()}
    except Exception:
        pass

load_state()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "✨ *Welcome to the Ultimate Multi-Channel Copy Bot!* ✨\n\n"
        "📜 *How to use me:*\n"
        "1️⃣ Use `/add @yourchannel` to add a channel to your quick-select menu.\n"
        "2️⃣ Use `/menu` to open the visual channel selector!\n"
        "3️⃣ Tap a channel button to lock onto it, then drop as many files as you want.\n\n"
        "⚡ _Make sure I am added as an Admin to your channels so I can post!_"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a channel to the user's saved list."""
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a channel username or ID to add.\n\nExample: `/add @strangerthings_channel`", parse_mode="Markdown")
        return
    
    channel = context.args[0]
    user_id = update.effective_user.id
    
    if user_id not in user_saved_channels:
        user_saved_channels[user_id] = []
        
    if channel not in user_saved_channels[user_id]:
        user_saved_channels[user_id].append(channel)
        
    user_destinations[user_id] = channel
    save_state()
    
    await update.message.reply_text(f"✅ Added {channel} to your menu!\n\n🎯 **Target Channel Locked to {channel}**.\nAny files sent now will go there.", parse_mode="Markdown")

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the inline keyboard menu to select a channel."""
    user_id = update.effective_user.id
    channels = user_saved_channels.get(user_id, [])
    
    if not channels:
        await update.message.reply_text("You haven't added any channels yet! Use `/add @yourchannel` first.")
        return
        
    keyboard = []
    for ch in channels:
        # Create a button for each saved channel. The callback_data is the channel ID/username.
        keyboard.append([InlineKeyboardButton(f"📡 {ch}", callback_data=f"set_{ch}")])
        
    keyboard.append([InlineKeyboardButton("🛑 Clear Target (Send to me)", callback_data="clear_target")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_target = user_destinations.get(user_id, "None (Private)")
    await update.message.reply_text(
        f"🎯 **Current Target:** {current_target}\n\nSelect a channel below to switch targets:", 
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the inline menu."""
    query = update.callback_query
    await query.answer() # Acknowledge the button click
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "clear_target":
        if user_id in user_destinations:
            del user_destinations[user_id]
        save_state()
        await query.edit_message_text("🛑 Target cleared! Files will be sent back to you privately.")
    elif data.startswith("set_"):
        channel = data[4:] # Extract channel from callback_data
        user_destinations[user_id] = channel
        save_state()
        await query.edit_message_text(f"✅ **Target Channel Locked!**\n\nDestination set to: {channel}\n\nDrop your files now!", parse_mode="Markdown")

async def copy_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
        
    user_id = update.effective_user.id
    chat_id_to_send = user_destinations.get(user_id, update.effective_chat.id)
    
    try:
        original_html = update.message.caption_html if update.message.caption else None
        
        if original_html:
            # Clean the caption: remove any line containing '@' or 't.me/'
            lines = original_html.split('\n')
            cleaned_lines = [line for line in lines if '@' not in line and 't.me/' not in line.lower()]
            cleaned_html = '\n'.join(cleaned_lines)
            
            await context.bot.copy_message(
                chat_id=chat_id_to_send,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
                caption=cleaned_html,
                parse_mode="HTML"
            )
        else:
            # No caption, just copy it normally
            await context.bot.copy_message(
                chat_id=chat_id_to_send,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send to `{chat_id_to_send}`. Are you sure I'm an admin there?\n\nError: {e}", parse_mode="Markdown")


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
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start_handler))
    application.add_handler(CommandHandler('add', add_channel))
    application.add_handler(CommandHandler('menu', show_menu))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, copy_message_handler))
    
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

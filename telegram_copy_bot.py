from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import re

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
user_saved_channels = {}
user_edit_mode = {}
pending_files = {} # prompt_id -> file data

def save_state():
    try:
        with open('bot_state.json', 'w') as f:
            json.dump({
                'dest': user_destinations, 
                'saved': user_saved_channels,
                'edit_mode': user_edit_mode
            }, f)
    except Exception:
        pass

def load_state():
    global user_destinations, user_saved_channels, user_edit_mode
    try:
        with open('bot_state.json', 'r') as f:
            data = json.load(f)
            user_destinations = {int(k): v for k, v in data.get('dest', {}).items()}
            user_saved_channels = {int(k): v for k, v in data.get('saved', {}).items()}
            user_edit_mode = {int(k): v for k, v in data.get('edit_mode', {}).items()}
    except Exception:
        pass

load_state()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "✨ *Welcome to the Ultimate Multi-Channel Copy Bot!* ✨\n\n"
        "📜 *How to use me:*\n"
        "1️⃣ Use `/add @yourchannel` to add a channel to your menu.\n"
        "2️⃣ Use `/menu` to open the visual channel selector!\n"
        "3️⃣ Tap a channel button to lock onto it, then drop files.\n\n"
        "🛠️ *Tools:*\n"
        "Use `/editmode on` to pause every file and allow you to type custom captions manually!\n\n"
        "⚡ _Make sure I am added as an Admin to your channels so I can post!_"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def toggle_editmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_mode = user_edit_mode.get(user_id, False)
    
    if not context.args:
        new_mode = not current_mode
    else:
        arg = context.args[0].lower()
        if arg == 'on':
            new_mode = True
        elif arg == 'off':
            new_mode = False
        else:
            new_mode = not current_mode
            
    user_edit_mode[user_id] = new_mode
    save_state()
    
    status = "🟢 ON" if new_mode else "🔴 OFF"
    msg = f"📝 **Manual Edit Mode:** {status}\n\n"
    if new_mode:
        msg += "When you send a file, the bot will now PAUSE and ask you for a custom caption before sending."
    else:
        msg += "Files will now be auto-cleaned and forwarded INSTANTLY."
        
    await update.message.reply_text(msg, parse_mode="Markdown")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    channels = user_saved_channels.get(user_id, [])
    
    if not channels:
        await update.message.reply_text("You haven't added any channels yet! Use `/add @yourchannel` first.")
        return
        
    keyboard = []
    for ch in channels:
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
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "clear_target":
        if user_id in user_destinations:
            del user_destinations[user_id]
        save_state()
        await query.edit_message_text("🛑 Target cleared! Files will be sent back to you privately.")
        
    elif data.startswith("set_"):
        channel = data[4:]
        user_destinations[user_id] = channel
        save_state()
        await query.edit_message_text(f"✅ **Target Channel Locked!**\n\nDestination set to: {channel}\n\nDrop your files now!", parse_mode="Markdown")
        
    elif data in ("sendasis", "cancel"):
        prompt_id = query.message.message_id
        if prompt_id not in pending_files:
            await query.edit_message_text("⚠️ This file has already been processed or expired.")
            return
            
        file_data = pending_files[prompt_id]
        
        if data == "sendasis":
            try:
                if file_data['original_cleaned_text']:
                    await context.bot.copy_message(
                        chat_id=file_data['chat_id_to_send'],
                        from_chat_id=file_data['from_chat_id'],
                        message_id=file_data['message_id'],
                        caption=file_data['original_cleaned_text'],
                        parse_mode="HTML"
                    )
                else:
                    await context.bot.copy_message(
                        chat_id=file_data['chat_id_to_send'],
                        from_chat_id=file_data['from_chat_id'],
                        message_id=file_data['message_id']
                    )
                await query.edit_message_text("✅ Sent as-is!")
            except Exception as e:
                await query.edit_message_text(f"❌ Failed to send: {e}")
                
        elif data == "cancel":
            await query.edit_message_text("❌ Cancelled. File was not sent.")
            
        del pending_files[prompt_id]

def format_caption(plain_text: str) -> str:
    lines = plain_text.split('\n')
    cleaned = [line for line in lines if '@' not in line and 't.me/' not in line.lower()]
    
    formatted_lines = []
    for line in cleaned:
        line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        kv_match = re.match(r'^(.*?)(Name|Size|Audio|Subtitle[s]?|Quality)(\s*:\s*)(.+)$', line, re.IGNORECASE)
        if kv_match:
            prefix = kv_match.group(1)
            key = kv_match.group(2)
            separator = kv_match.group(3)
            value = kv_match.group(4)
            formatted_lines.append(f"{prefix}{key}{separator}<code>{value}</code>")
            continue
            
        if re.search(r'\.(mkv|mp4|avi)\s*$', line, re.IGNORECASE):
            formatted_lines.append(f"<code>{line}</code>")
            continue
            
        formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)

async def copy_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
        
    user_id = update.effective_user.id
    
    # 1. Check if this is a TEXT REPLY to a prompt
    if update.message.text and update.message.reply_to_message:
        prompt_id = update.message.reply_to_message.message_id
        if prompt_id in pending_files:
            file_data = pending_files[prompt_id]
            new_caption = format_caption(update.message.text) # Apply standard format even to manual edits
            
            try:
                await context.bot.copy_message(
                    chat_id=file_data['chat_id_to_send'],
                    from_chat_id=file_data['from_chat_id'],
                    message_id=file_data['message_id'],
                    caption=new_caption,
                    parse_mode="HTML"
                )
                await update.message.reply_to_message.edit_text("✅ Sent with your custom text!")
                del pending_files[prompt_id]
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send: {e}")
            return
            
    # 2. Otherwise, treat as an incoming file to forward
    chat_id_to_send = user_destinations.get(user_id, update.effective_chat.id)
    is_edit_mode = user_edit_mode.get(user_id, False)
    
    try:
        cleaned_text = format_caption(update.message.caption) if update.message.caption else None
        
        if is_edit_mode:
            # Hold the file and prompt
            keyboard = [
                [InlineKeyboardButton("➡️ Send As-Is (Original Text)", callback_data="sendasis")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            
            # Show them what the auto-cleaned text looks like
            preview = f"<pre>{cleaned_text}</pre>" if cleaned_text else "<i>(No text)</i>"
            
            prompt_msg = await update.message.reply_text(
                f"📝 **File Paused!**\n\nTo add your custom text, **REPLY** to this message with your new text.\n\n_Auto-Cleaned Original:_ \n{preview}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
            
            pending_files[prompt_msg.message_id] = {
                'chat_id_to_send': chat_id_to_send,
                'from_chat_id': update.effective_chat.id,
                'message_id': update.message.message_id,
                'original_cleaned_text': cleaned_text
            }
        else:
            # Send immediately
            if cleaned_text:
                await context.bot.copy_message(
                    chat_id=chat_id_to_send,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                    caption=cleaned_text,
                    parse_mode="HTML"
                )
            else:
                await context.bot.copy_message(
                    chat_id=chat_id_to_send,
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
                
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to process.\n\nError: {e}", parse_mode="Markdown")

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
    application.add_handler(CommandHandler('editmode', toggle_editmode))
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

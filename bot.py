import os
import json
import logging
import threading
import time
import schedule
from datetime import datetime
import importlib.util

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Attempt to import main. If not found, open file explorer to select main.py.
try:
    import main
except ImportError:
    from tkinter import Tk, filedialog
    Tk().withdraw()
    main_path = filedialog.askopenfilename(
        title="Select your main.py file",
        filetypes=[("Python Files", "*.py")]
    )
    if not main_path:
        raise ImportError("main.py not selected. Exiting.")
    spec = importlib.util.spec_from_file_location("main", main_path)
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_config():
    return main.load_config()

# /start command: shows a menu with options.
def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Run STATIC Analysis (9AM)", callback_data='run_static')],
        [InlineKeyboardButton("Run DYNAMIC Analysis (14:15)", callback_data='run_dynamic')],
        [InlineKeyboardButton("List Stock Lists", callback_data='list_stocklists')],
        [InlineKeyboardButton("Show Status", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Welcome! Please choose an option:", reply_markup=reply_markup)

# /help command: lists available commands.
def help_command(update: Update, context: CallbackContext):
    help_text = (
        "Available commands:\n"
        "/start - Show main menu\n"
        "/help - Show this help message\n"
        "/set_config <parameter> <value> - Update a configuration parameter\n"
        "/run_static - Force run STATIC analysis immediately\n"
        "/run_dynamic - Force run DYNAMIC analysis immediately\n"
        "/list_stocklists - List available stock lists\n"
        "/status - Show current configuration status\n"
        "/update_config - Reload configuration from file\n"
        "/set_static_time <HH:MM> - Set static analysis time\n"
        "/set_dynamic_time <HH:MM> - Set dynamic analysis time\n"
        "/restart_bot - Restart the bot (reload configuration)"
    )
    update.message.reply_text(help_text)

# /set_config command: update a config parameter.
def set_config(update: Update, context: CallbackContext):
    args = context.args
    if len(args) != 2:
        update.message.reply_text("Usage: /set_config <parameter> <value>")
        return
    param, value = args
    config = get_config()
    if param in config:
        try:
            current_value = config[param]
            if isinstance(current_value, bool):
                config[param] = value.lower() == 'true'
            elif isinstance(current_value, int):
                config[param] = int(value)
            elif isinstance(current_value, float):
                config[param] = float(value)
            else:
                config[param] = value
            config_path = main.get_stored_config_path()
            if config_path:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                update.message.reply_text(f"Updated {param} to {value}.")
            else:
                update.message.reply_text("Config file path not found.")
        except Exception as e:
            update.message.reply_text(f"Error updating config: {e}")
    else:
        update.message.reply_text("Parameter not found in config.")

# /run_static command: force static analysis.
def run_static_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("Running STATIC analysis now...")
    threading.Thread(target=main.run_static_analysis, daemon=True).start()

# /run_dynamic command: force dynamic analysis.
def run_dynamic_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("Running DYNAMIC analysis now...")
    threading.Thread(target=main.run_dynamic_analysis, daemon=True).start()

# /list_stocklists command: list stock lists.
def list_stocklists(update: Update, context: CallbackContext):
    config = get_config()
    stock_lists = config.get("STOCK_LISTS", {})
    if not stock_lists:
        update.message.reply_text("No stock lists defined in config.")
        return
    msg = "Available stock lists:\n" + "\n".join(list(stock_lists.keys()))
    update.message.reply_text(msg)

# /status command: show configuration.
def status(update: Update, context: CallbackContext):
    config = get_config()
    msg = "Current configuration:\n" + "\n".join([f"{k}: {v}" for k, v in config.items()])
    update.message.reply_text(msg)

# /update_config command: reload configuration.
def update_config(update: Update, context: CallbackContext):
    config = main.load_config()
    update.message.reply_text("Configuration reloaded.")

# Extra commands.
def set_static_time(update: Update, context: CallbackContext):
    return set_config(update, context)

def set_dynamic_time(update: Update, context: CallbackContext):
    return set_config(update, context)

def restart_bot(update: Update, context: CallbackContext):
    update.message.reply_text("Restarting bot...")
    main.load_config()
    update.message.reply_text("Bot restarted (configuration reloaded).")

# Inline button callback.
def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == "run_static":
        query.edit_message_text("Starting STATIC analysis...")
        threading.Thread(target=main.run_static_analysis, daemon=True).start()
    elif data == "run_dynamic":
        query.edit_message_text("Starting DYNAMIC analysis...")
        threading.Thread(target=main.run_dynamic_analysis, daemon=True).start()
    elif data == "list_stocklists":
        config = get_config()
        stock_lists = config.get("STOCK_LISTS", {})
        if not stock_lists:
            query.edit_message_text("No stock lists defined in config.")
            return
        keyboard = [[InlineKeyboardButton(key, callback_data=f"select_{key}")] for key in stock_lists.keys()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Select a stock list:", reply_markup=reply_markup)
    elif data.startswith("select_"):
        selected = data.split("select_")[1]
        query.edit_message_text(f"Selected stock list: {selected}. Running both analyses now...")
        threading.Thread(target=main.run_static_analysis, daemon=True).start()
        threading.Thread(target=main.run_dynamic_analysis, daemon=True).start()
    elif data == "status":
        config = get_config()
        msg = "Current configuration:\n" + "\n".join([f"{k}: {v}" for k, v in config.items()])
        query.edit_message_text(msg)

# Daily prompt at 09:00.
def schedule_daily_prompt(context: CallbackContext):
    config = get_config()
    chat_id = config.get("TELEGRAM_CHAT_ID")
    context.bot.send_message(chat_id=chat_id, text="Good morning! Do you want to run the analysis today? Use /start to begin.")

def main_bot():
    config = get_config()
    token = config.get("TELEGRAM_BOT_TOKEN")
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("set_config", set_config))
    dp.add_handler(CommandHandler("run_static", run_static_cmd))
    dp.add_handler(CommandHandler("run_dynamic", run_dynamic_cmd))
    dp.add_handler(CommandHandler("list_stocklists", list_stocklists))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("update_config", update_config))
    dp.add_handler(CommandHandler("set_static_time", set_static_time))
    dp.add_handler(CommandHandler("set_dynamic_time", set_dynamic_time))
    dp.add_handler(CommandHandler("restart_bot", restart_bot))
    dp.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()

    schedule.every().day.at("09:00").do(lambda: updater.bot.send_message(chat_id=config.get("TELEGRAM_CHAT_ID"), text="Good morning! Do you want to run the analysis today? Use /start to begin."))
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)
    threading.Thread(target=run_schedule, daemon=True).start()

    updater.idle()

if __name__ == '__main__':
    main_bot()

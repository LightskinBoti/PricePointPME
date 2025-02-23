import json
import time
import os
from datetime import datetime, timedelta
import requests
import threading
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import tkinter
from tkinter import filedialog, Tk

from data_fetch import fetch_static_data, fetch_dynamic_data, dump_data_to_csv, dump_data_to_json
from data_filterPM import filter_opportunities
from telegram import send_opportunity_message, send_telegram_message

CONFIG_PATH_FILE = "config_path.txt"  # persistent file storing the config.json path

def get_stored_config_path():
    if os.path.exists(CONFIG_PATH_FILE):
        with open(CONFIG_PATH_FILE, "r") as f:
            stored_path = f.read().strip()
            if stored_path and os.path.exists(stored_path):
                return stored_path
    return None

def save_config_path(config_path):
    with open(CONFIG_PATH_FILE, "w") as f:
        f.write(config_path)

def load_config():
    config_path = get_stored_config_path()
    if not config_path:
        print("Could not find 'config.json'. Opening file explorer...")
        root = Tk()
        root.withdraw()
        config_path = filedialog.askopenfilename(
            title="Select your config.json file",
            filetypes=[("JSON Files", "*.json")]
        )
        if not config_path:
            raise FileNotFoundError("No config file selected. Exiting.")
        else:
            save_config_path(config_path)
    with open(config_path, "r") as f:
        config = json.load(f)
    print("Loaded config from:", config_path)
    print("DEV_MODE =", config.get("DEV_MODE", False))
    return config

##############################################
# Run static analysis at 9:00 (or configured) #
##############################################
def run_static_analysis():
    config = load_config()
    stock_lists = config.get("STOCK_LISTS", {})
    if not stock_lists:
        send_telegram_message(config, "No stock lists defined in config.")
        return
    # Choose default stock list (or extend to let user choose)
    selected_list_name = list(stock_lists.keys())[0]
    stock_list = stock_lists[selected_list_name]
    wait_time = config.get("WAIT_TIME_BETWEEN_STOCKS", 2)
    send_telegram_message(config, f"Starting STATIC analysis for list '{selected_list_name}' at 09:00.")
    static_results = fetch_static_data(stock_list)
    # Save static data for later use
    with open("static_results.json", "w") as f:
        json.dump(static_results, f, indent=2)
    send_telegram_message(config, "Static analysis completed successfully at 09:00.")

##############################################
# Run dynamic analysis at 14:15 (or configured)#
##############################################
def run_dynamic_analysis():
    config = load_config()
    stock_lists = config.get("STOCK_LISTS", {})
    if not stock_lists:
        send_telegram_message(config, "No stock lists defined in config.")
        return
    selected_list_name = list(stock_lists.keys())[0]
    stock_list = stock_lists[selected_list_name]
    wait_time = config.get("WAIT_TIME_BETWEEN_STOCKS", 2)
    tv_cookies = config.get("TV_COOKIES", [])
    send_telegram_message(config, f"Starting DYNAMIC analysis for list '{selected_list_name}' at 14:15.")
    dynamic_data, dyn_total, dyn_avg = fetch_dynamic_data(stock_list, tv_cookies, wait_time)
    try:
        with open("static_results.json", "r") as f:
            static_results = json.load(f)
    except Exception as e:
        send_telegram_message(config, f"Error loading static results: {e}")
        static_results = {}
    final_results = []
    for symbol in stock_list:
        sdata = static_results.get(symbol, {})
        ddata = dynamic_data.get(symbol, {})
        price = ddata.get("price", "N/A")
        sma = sdata.get("sma")
        position = "N/A"
        try:
            if price != "N/A" and sma:
                price_val = float(price.replace(",", ""))
                sma_val = float(str(sma).replace(",", ""))
                position = "Above SMA" if price_val > sma_val else "Below SMA"
        except Exception:
            pass
        record = {
            "symbol": symbol,
            "rsi": sdata.get("rsi"),
            "sma": sma,
            "position": position,
            "price": price,
            "premarket_price": ddata.get("premarket_price", "N/A"),
            "premarket_change": ddata.get("premarket_change", "N/A"),
            "premarket_change_percent": ddata.get("premarket_change_percent", "N/A")
        }
        final_results.append(record)
    dump_data_to_csv(final_results)
    dump_data_to_json(final_results)
    opportunities = filter_opportunities(final_results, config)
    send_telegram_message(config, "Dynamic analysis completed successfully at 14:15.")
    send_opportunity_message(config, opportunities)

##############################################
# Scheduler: static analysis at 9:00, dynamic at 14:15
##############################################
def schedule_run():
    config = load_config()
    dev_mode = config.get("DEV_MODE", False)
    if dev_mode:
        print("DEV_MODE is ON – running both analyses immediately.")
        run_static_analysis()
        run_dynamic_analysis()
        return
    now = datetime.now()
    # Get static analysis time from config; defaults to 09:00
    static_hour = config.get("STATIC_ANALYSIS_HOUR", 9)
    static_minute = config.get("STATIC_ANALYSIS_MINUTE", 0)
    static_time = now.replace(hour=static_hour, minute=static_minute, second=0, microsecond=0)
    if static_time <= now:
        static_time += timedelta(days=1)
    static_delay = (static_time - now).total_seconds()
    print(f"Scheduled STATIC analysis at {static_time.strftime('%H:%M:%S')}. Waiting {int(static_delay)} seconds...")
    send_telegram_message(config, f"Scheduled STATIC analysis for {static_time.strftime('%H:%M:%S')}.")
    threading.Timer(static_delay, run_static_analysis).start()
    
    # Get dynamic analysis time from config; defaults to 14:15
    dynamic_hour = config.get("DYNAMIC_ANALYSIS_HOUR", 14)
    dynamic_minute = config.get("DYNAMIC_ANALYSIS_MINUTE", 15)
    dynamic_time = now.replace(hour=dynamic_hour, minute=dynamic_minute, second=0, microsecond=0)
    if dynamic_time <= now:
        dynamic_time += timedelta(days=1)
    dynamic_delay = (dynamic_time - now).total_seconds()
    print(f"Scheduled DYNAMIC analysis at {dynamic_time.strftime('%H:%M:%S')}. Waiting {int(dynamic_delay)} seconds...")
    send_telegram_message(config, f"Scheduled DYNAMIC analysis for {dynamic_time.strftime('%H:%M:%S')}.")
    threading.Timer(dynamic_delay, run_dynamic_analysis).start()

if __name__ == "__main__":
    schedule_run()

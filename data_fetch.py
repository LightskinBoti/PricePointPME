import os
import json
import time
import logging
import datetime
from tkinter import Tk, filedialog

from tradingview_ta import TA_Handler, Interval
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from playwright.sync_api import sync_playwright

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

############################
# Utility Functions
############################

def load_cookies(file_path="cookies.json"):
    """
    Loads cookies from a JSON file. If not found, opens a file explorer to select a JSON file.
    """
    if not os.path.isfile(file_path):
        console.print(f"[yellow]'{file_path}' not found. Please select the cookies file.[/yellow]")
        root = Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Select cookies.json file",
            filetypes=[("JSON files", "*.json")]
        )
        if not file_path:
            console.print("[red]No file selected. Exiting...[/red]")
            exit(1)
        console.print(f"[green]Loaded cookies from: {file_path}[/green]")
    try:
        with open(file_path, "r") as f:
            cookies = json.load(f)
        return cookies
    except Exception as e:
        console.print(f"[red]Error loading cookies: {e}[/red]")
        exit(1)

def get_symbol_variants(symbol):
    """
    Returns a list of possible symbol variants.
    For example, if a symbol contains a hyphen (e.g. "BRK-A"), also try "BRK.A".
    """
    variants = [symbol]
    if '-' in symbol:
        variants.append(symbol.replace('-', '.'))
    return variants

############################
# 1) Static Data Fetching
############################

def fetch_static_data(stock_list):
    """
    Fetch static data (RSI and SMA) for each stock in the list.
    Tries each symbol variant first on NASDAQ, then on NYSE.
    """
    static_results = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        task_id = progress.add_task("Fetching RSI & SMA (static)...", total=len(stock_list))
        for symbol in stock_list:
            rsi, sma = None, None
            found = False
            variants = get_symbol_variants(symbol)
            for variant in variants:
                for exchange in ["NASDAQ", "NYSE"]:
                    try:
                        handler = TA_Handler(
                            symbol=variant,
                            screener="america",
                            exchange=exchange,
                            interval=Interval.INTERVAL_1_DAY
                        )
                        analysis = handler.get_analysis()
                        rsi = analysis.indicators.get("RSI")
                        sma = analysis.indicators.get("SMA20")
                        if rsi is not None and sma is not None:
                            found = True
                            break  # Successfully fetched data for this variant/exchange
                    except Exception as e:
                        if "Exchange or symbol not found" in str(e):
                            continue
                        else:
                            logger.debug("Error fetching static data for %s (%s) on %s: %s", symbol, variant, exchange, e)
                if found:
                    break
            static_results[symbol] = {"rsi": rsi, "sma": sma}
            progress.update(task_id, advance=1)
            time.sleep(0.1)
    return static_results

############################
# 2) Dynamic Data Fetching
############################

def fetch_dynamic_data(stock_list, cookies, wait_time):
    """
    Scrapes dynamic data (price and pre-market info) for each stock using Playwright.
    """
    overall_start_time = time.time()
    total_fetch_time = 0.0
    dynamic_results = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True
    ) as progress:
        task_id = progress.add_task("Scraping dynamic data (price, pre-market)...", total=len(stock_list))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()
            # Open a sample TradingView chart page
            page.goto("https://www.tradingview.com/chart/RRIUvF6a/?symbol=NASDAQ:AAPL")
            for idx, symbol in enumerate(stock_list, start=1):
                start_time_per_stock = time.time()
                # Clear previous input
                for _ in range(15):
                    page.keyboard.press("Backspace")
                page.keyboard.type(symbol)
                page.keyboard.press("Enter")
                try:
                    page.wait_for_selector('span.price-qWcO4bp9', timeout=3000)
                except Exception:
                    pass
                real_time_price = page.query_selector('span.price-qWcO4bp9')
                pre_market_price = page.query_selector('span.price-d1N3lNBX')
                pre_market_change_percent = page.query_selector('span.changePercent-d1N3lNBX')
                dynamic_results[symbol] = {
                    "price": real_time_price.inner_text().strip() if real_time_price else "N/A",
                    "premarket_price": pre_market_price.inner_text().strip() if pre_market_price else "N/A",
                    "premarket_change": "N/A",
                    "premarket_change_percent": pre_market_change_percent.inner_text().strip() if pre_market_change_percent else "N/A"
                }
                stock_time = time.time() - start_time_per_stock
                total_fetch_time += stock_time
                console.print(
                    f"({idx}/{len(stock_list)}) {symbol} => Price: {dynamic_results[symbol]['price']}, "
                    f"PM: {dynamic_results[symbol]['premarket_price']}, PM%: {dynamic_results[symbol]['premarket_change_percent']}, "
                    f"Time: {stock_time:.2f}s"
                )
                progress.update(task_id, advance=1)
                time.sleep(wait_time)
            browser.close()
    overall_time = time.time() - overall_start_time
    avg_time_per_stock = total_fetch_time / len(stock_list) if stock_list else 0
    console.print(f"[green]Analyzed {len(stock_list)} stocks in {overall_time:.2f} seconds total.[/green]")
    console.print(f"[green]Average fetch time per stock: {avg_time_per_stock:.2f}s[/green]")
    return dynamic_results, overall_time, avg_time_per_stock

############################
# 3) Combined Data Fetching
############################

def fetch_all_stocks(stock_list, cookies, wait_time):
    """
    Fetch both static and dynamic data for all stocks and combine results.
    """
    static_data = fetch_static_data(stock_list)
    dynamic_data, dyn_total, dyn_avg = fetch_dynamic_data(stock_list, cookies, wait_time)
    final_results = []
    for symbol in stock_list:
        rsi_sma = static_data.get(symbol, {})
        dyn = dynamic_data.get(symbol, {})
        price = dyn.get("price", "N/A")
        sma = rsi_sma.get("sma")
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
            "rsi": rsi_sma.get("rsi"),
            "sma": sma,
            "position": position,
            "price": price,
            "premarket_price": dyn.get("premarket_price", "N/A"),
            "premarket_change": dyn.get("premarket_change", "N/A"),
            "premarket_change_percent": dyn.get("premarket_change_percent", "N/A")
        }
        final_results.append(record)
    final_results.append({
        "symbol": "__DYNAMIC_SCRAPE_STATS__",
        "dynamic_scrape_total_seconds": f"{dyn_total:.2f}",
        "dynamic_scrape_avg_seconds": f"{dyn_avg:.2f}"
    })
    return final_results

############################
# 4) Data Dump Utilities
############################

def dump_data_to_csv(data, filename=None):
    import csv
    filename = filename or datetime.datetime.now().strftime("%Y-%m-%d") + ".csv"
    fieldnames = [
        "symbol", "price", "rsi", "sma", "position",
        "premarket_price", "premarket_change", "premarket_change_percent",
        "dynamic_scrape_total_seconds", "dynamic_scrape_avg_seconds"
    ]
    try:
        with open(filename, "w", newline="", encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        console.print(f"[green]Data dumped to CSV: {filename}[/green]")
    except Exception as e:
        console.print(f"[red]Error dumping CSV: {e}[/red]")

def dump_data_to_json(data, filename=None):
    filename = filename or datetime.datetime.now().strftime("%Y-%m-%d") + ".json"
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"[green]Data dumped to JSON: {filename}[/green]")
    except Exception as e:
        console.print(f"[red]Error dumping JSON: {e}[/red]")

import json
from datetime import datetime
from rich.console import Console

console = Console()

def filter_premarket_data(input_filename, output_filename=None):
    """
    Reads raw data from input_filename, calculates:
      premarket_change_percent = (premarket_change / price) * 100
    Only stocks with valid data are kept.
    Writes the filtered data to output_filename (default: YYYY-MM-DD_filtered.json).
    Returns (output_filename, filtered_list).
    """
    try:
        with open(input_filename, "r") as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[red]Error reading {input_filename}: {e}[/red]")
        return None, []

    filtered = []
    for stock in data:
        if stock.get("symbol") == "__DYNAMIC_SCRAPE_STATS__":
            filtered.append(stock)
            continue
        if "error" in stock:
            continue
        price_str = str(stock.get("price", "N/A")).replace(",", "")
        change_str = str(stock.get("premarket_change", "N/A")).replace(",", "")
        if price_str.upper() == "N/A" or change_str.upper() == "N/A":
            stock["premarket_change_percent"] = "N/A"
            filtered.append(stock)
            continue
        try:
            price = float(price_str)
            change = float(change_str)
            if price != 0:
                stock["premarket_change_percent"] = (change / price) * 100
            else:
                stock["premarket_change_percent"] = "N/A"
            filtered.append(stock)
        except Exception as e:
            console.print(f"[red]Error filtering {stock.get('symbol')}: {e}[/red]")
            continue

    if output_filename is None:
        output_filename = datetime.now().strftime("%Y-%m-%d") + "_filtered.json"
    try:
        with open(output_filename, "w") as f:
            json.dump(filtered, f, indent=2)
        console.print(f"[green]Filtered data dumped to {output_filename}[/green]")
    except Exception as e:
        console.print(f"[red]Error dumping filtered JSON: {e}[/red]")
    return output_filename, filtered

def filter_opportunities(filtered_data, config):
    """
    Ranks long and short candidates based on RSI and premarket change.
    - 'long' if RSI < RSI_SHORT_MIN and premarket_change_percent >= MIN_PREMARKET_CHANGE_PERCENT
    - 'short' if RSI > RSI_LONG_MAX and premarket_change_percent <= -MIN_PREMARKET_CHANGE_PERCENT
    """
    rsi_long_max = config.get("RSI_LONG_MAX", 70)
    rsi_short_min = config.get("RSI_SHORT_MIN", 30)
    min_pm_change = config.get("MIN_PREMARKET_CHANGE_PERCENT", 2.0)

    long_candidates = []
    short_candidates = []

    for stock in filtered_data:
        if stock.get("symbol") == "__DYNAMIC_SCRAPE_STATS__":
            continue
        if "error" in stock:
            continue
        rsi = stock.get("rsi")
        pmchg_pct = stock.get("premarket_change_percent")
        if (rsi is not None) and (pmchg_pct is not None) and pmchg_pct != "N/A":
            try:
                if float(rsi) < rsi_short_min and float(pmchg_pct) >= min_pm_change:
                    long_candidates.append(stock)
                if float(rsi) > rsi_long_max and float(pmchg_pct) <= -min_pm_change:
                    short_candidates.append(stock)
            except Exception:
                continue

    long_candidates = sorted(long_candidates, key=lambda x: x["premarket_change_percent"] if x["premarket_change_percent"] != "N/A" else 0, reverse=True)
    short_candidates = sorted(short_candidates, key=lambda x: x["premarket_change_percent"] if x["premarket_change_percent"] != "N/A" else 0)
    return {"long": long_candidates, "short": short_candidates}

if __name__ == "__main__":
    today_file = datetime.now().strftime("%Y-%m-%d") + ".json"
    _, filtered_data = filter_premarket_data(today_file)
    mock_config = {
        "RSI_LONG_MAX": 70,
        "RSI_SHORT_MIN": 30,
        "MIN_PREMARKET_CHANGE_PERCENT": 2.0
    }
    opportunities = filter_opportunities(filtered_data, mock_config)
    console.print(opportunities)

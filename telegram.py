import requests
from rich.console import Console

console = Console()

def send_telegram_message(config, text):
    """
    Sends a plain text message to the Telegram chat specified in config.
    """
    token = config.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        console.print("[red]Telegram config missing.[/red]")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        console.print(f"[red]Error sending Telegram message: {e}[/red]")

def send_opportunity_message(config, opportunities):
    """
    Formats and sends the top opportunities (long and short) via Telegram.
    """
    lines = []
    lines.append("Top Opportunities:")
    if opportunities["long"]:
        lines.append("**LONG Positions:**")
        for stock in opportunities["long"]:
            rsi_val = f"{stock['rsi']:.2f}" if stock.get('rsi') is not None else "N/A"
            sma_val = f"{stock['sma']:.2f}" if stock.get('sma') is not None else "N/A"
            pmc_val = stock.get('premarket_change_percent', "N/A")
            line = f"{stock['symbol']} | Price: {stock['price']} | RSI: {rsi_val} | SMA: {sma_val} | PreMkt%: {pmc_val}"
            lines.append(line)
    else:
        lines.append("No LONG opportunities found.")
    lines.append("")
    if opportunities["short"]:
        lines.append("**SHORT Positions:**")
        for stock in opportunities["short"]:
            rsi_val = f"{stock['rsi']:.2f}" if stock.get('rsi') is not None else "N/A"
            sma_val = f"{stock['sma']:.2f}" if stock.get('sma') is not None else "N/A"
            pmc_val = stock.get('premarket_change_percent', "N/A")
            line = f"{stock['symbol']} | Price: {stock['price']} | RSI: {rsi_val} | SMA: {sma_val} | PreMkt%: {pmc_val}"
            lines.append(line)
    else:
        lines.append("No SHORT opportunities found.")
    message = "\n".join(lines)
    send_telegram_message(config, message)

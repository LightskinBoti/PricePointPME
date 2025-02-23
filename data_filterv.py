import json
from data_filterPM import filter_premarket_data, filter_opportunities

# This file is maintained for backward compatibility.
# Use functions from data_filterPM.py instead.
if __name__ == "__main__":
    from datetime import datetime
    today_file = datetime.now().strftime("%Y-%m-%d") + ".json"
    _, filtered_data = filter_premarket_data(today_file)
    config = {
        "RSI_LONG_MAX": 70,
        "RSI_SHORT_MIN": 30,
        "MIN_PREMARKET_CHANGE_PERCENT": 2.0
    }
    opportunities = filter_opportunities(filtered_data, config)
    print(opportunities)

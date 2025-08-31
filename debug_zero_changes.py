#!/usr/bin/env python3

# Debug why all changes are 0.0%
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

print("🔍 Debugging 0.0% Changes Issue")
print("=" * 40)

# Load historical data directly
with open('data/fx_historical_rates.json', 'r') as f:
    historical_data = json.load(f)

print(f"📊 Historical data loaded: {len(historical_data)} dates")
for date in sorted(historical_data.keys()):
    rates = historical_data[date]['rates']
    print(f"  {date}: NZD/USD={rates['NZD/USD']}, USD/BTC={rates['USD/BTC']}")

print(f"\n📅 Date calculations:")
now = datetime.now()
print(f"Current datetime: {now}")
for days_ago in [1, 7, 30]:
    target_date = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    print(f"  {days_ago} days ago: {target_date}")
    
    if target_date in historical_data:
        print(f"    ✅ Found exact date")
    else:
        print(f"    ❌ Not found, would use fallback")

print(f"\n🧪 Testing _get_historical_rates function:")
from foreign_exchange_data import _get_historical_rates

for days_ago in [1, 7, 30]:
    result = _get_historical_rates(days_ago)
    print(f"  {days_ago} days ago:")
    if result:
        print(f"    ✅ Got rates: NZD/USD={result.get('NZD/USD')}, USD/BTC={result.get('USD/BTC')}")
    else:
        print(f"    ❌ No rates returned")

print(f"\n🔢 Testing percentage calculations:")
from foreign_exchange_data import _calculate_percentage_change

# Test with known values
test_cases = [
    ("Same values", 0.589, 0.589, 0.0),
    ("Current higher", 0.589, 0.580, 1.6),  # (0.589-0.580)/0.580 * 100
    ("Current lower", 0.580, 0.589, -1.5),  # (0.580-0.589)/0.589 * 100
]

for desc, current, historical, expected in test_cases:
    result = _calculate_percentage_change(current, historical)
    print(f"  {desc}: {result:.1f}% (expected: {expected:.1f}%)")

print(f"\n🚀 Testing current vs historical rate lookup:")

# Get current rates
from foreign_exchange_data import _fetch_traditional_fx_rates, _fetch_crypto_rates

current_traditional = _fetch_traditional_fx_rates()
current_crypto = _fetch_crypto_rates()

print(f"Current traditional rates:")
if current_traditional:
    for pair, rate in current_traditional.items():
        print(f"  {pair}: {rate}")

print(f"Current crypto rates:")
if current_crypto:
    for pair, rate in current_crypto.items():
        print(f"  {pair}: {rate}")

# Compare with historical
print(f"\n📊 Manual comparison:")
historical_1d = _get_historical_rates(1)
historical_7d = _get_historical_rates(7)

if current_traditional and historical_1d:
    for pair in current_traditional:
        if pair in historical_1d:
            current = current_traditional[pair]
            historical = historical_1d[pair]
            change = _calculate_percentage_change(current, historical)
            print(f"  {pair}: current={current}, 1d_ago={historical}, change={change:.1f}%")

if current_crypto and historical_1d:
    for pair in current_crypto:
        if pair in historical_1d:
            current_str = current_crypto[pair]
            historical_str = historical_1d[pair]
            
            # Convert strings to numbers
            current_num = float(current_str.replace(',', ''))
            historical_num = float(historical_str.replace(',', ''))
            
            change = _calculate_percentage_change(current_num, historical_num)
            print(f"  {pair}: current={current_str}, 1d_ago={historical_str}, change={change:.1f}%")

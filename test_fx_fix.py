#!/usr/bin/env python3

# Quick test of the fixed FX historical lookup
import sys
import os
sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

print("🔧 Testing Fixed FX Historical Lookup")
print("=" * 40)

# Test the _get_historical_rates function
from foreign_exchange_data import _get_historical_rates, _load_historical_data

# Show what dates we have
historical_data = _load_historical_data()
available_dates = sorted(historical_data.keys())
print(f"📅 Available historical dates: {available_dates}")

# Test each window
windows = [('24h', 1), ('7d', 7), ('30d', 30)]

print(f"\n🧪 Testing each time window:")
for window_name, days_ago in windows:
    print(f"\n--- {window_name} ({days_ago} days ago) ---")
    result = _get_historical_rates(days_ago)
    
    if result:
        print(f"✅ SUCCESS: Got {len(result)} currency pairs")
        for pair in ['NZD/USD', 'USD/BTC']:
            if pair in result:
                print(f"  {pair}: {result[pair]}")
    else:
        print(f"❌ FAILED: No data returned")

print(f"\n🚀 Testing full FX pipeline:")
from foreign_exchange_data import pull_fx_data

result = pull_fx_data()
if result.get('status') == 'success':
    print("✅ Full pipeline working!")
    for pair, data in result.get('rates', {}).items():
        changes = data.get('changes', {})
        if changes:
            change_strs = [f"{k}: {v:+.1f}%" for k, v in changes.items()]
            print(f"  {pair}: {', '.join(change_strs)}")
        else:
            print(f"  {pair}: No changes available")

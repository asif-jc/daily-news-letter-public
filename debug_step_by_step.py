#!/usr/bin/env python3

# DEBUG: Simple step-by-step debugging
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

print("🔍 DEBUGGING FX SYSTEM - STEP BY STEP")
print("=" * 50)

# STEP 1: Check if historical data file exists and has data
print("\n1️⃣ CHECKING HISTORICAL DATA FILE")
data_file = 'data/fx_historical_rates.json'

if os.path.exists(data_file):
    with open(data_file, 'r') as f:
        historical_data = json.load(f)
    print(f"✅ File exists with {len(historical_data)} entries")
    
    dates = sorted(historical_data.keys())
    print(f"📅 Dates: {dates[0]} to {dates[-1]}")
else:
    print("❌ Historical data file does not exist!")
    exit(1)

# STEP 2: Test date calculations
print("\n2️⃣ TESTING DATE CALCULATIONS")
now = datetime.now()
print(f"Current datetime: {now}")

for days_ago in [1, 7, 30]:
    target_date = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    exists = target_date in historical_data
    print(f"  {days_ago} days ago: {target_date} {'✅' if exists else '❌'}")

# STEP 3: Test the _get_historical_rates function
print("\n3️⃣ TESTING _get_historical_rates FUNCTION")

try:
    from foreign_exchange_data import _get_historical_rates
    
    for days_ago in [1, 7, 30]:
        print(f"\nTesting {days_ago} days ago:")
        result = _get_historical_rates(days_ago)
        
        if result:
            print(f"  ✅ Got data: {len(result)} pairs")
            print(f"  Sample: NZD/USD = {result.get('NZD/USD', 'MISSING')}")
        else:
            print(f"  ❌ No data returned")
            
except Exception as e:
    print(f"❌ Error importing/testing function: {e}")

# STEP 4: Test current rate fetching
print("\n4️⃣ TESTING CURRENT RATE FETCHING")

try:
    from foreign_exchange_data import _fetch_traditional_fx_rates, _fetch_crypto_rates
    
    print("Fetching current traditional rates...")
    current_traditional = _fetch_traditional_fx_rates()
    if current_traditional:
        print(f"✅ Got {len(current_traditional)} traditional rates")
        for pair, rate in current_traditional.items():
            print(f"  {pair}: {rate}")
    else:
        print("❌ No traditional rates")
    
    print("\nFetching current crypto rates...")
    current_crypto = _fetch_crypto_rates()
    if current_crypto:
        print(f"✅ Got {len(current_crypto)} crypto rates")
        for pair, rate in current_crypto.items():
            print(f"  {pair}: {rate}")
    else:
        print("❌ No crypto rates")
        
except Exception as e:
    print(f"❌ Error fetching current rates: {e}")

# STEP 5: Manual percentage calculation test
print("\n5️⃣ TESTING PERCENTAGE CALCULATIONS")

try:
    from foreign_exchange_data import _calculate_percentage_change
    
    # Test with known values
    test_cases = [
        ("0.589 vs 0.591", 0.589, 0.591),  # Should be negative
        ("0.589 vs 0.587", 0.589, 0.587),  # Should be positive
        ("Same values", 0.589, 0.589),     # Should be 0
    ]
    
    for desc, current, historical in test_cases:
        change = _calculate_percentage_change(current, historical)
        print(f"  {desc}: {change:.2f}%")
        
except Exception as e:
    print(f"❌ Error testing calculations: {e}")

print(f"\n🎯 SUMMARY:")
print(f"If all steps above show ✅, the system should work.")
print(f"If any step shows ❌, that's where the problem is.")

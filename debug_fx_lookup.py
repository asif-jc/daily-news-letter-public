#!/usr/bin/env python3

# Debug the FX historical data lookup issue
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

def debug_fx_historical_lookup():
    """Debug why only 24h window is working"""
    
    os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
    
    print("🔍 Debugging FX Historical Data Lookup")
    print("=" * 50)
    
    # Check if historical data file exists
    data_file = 'data/fx_historical_rates.json'
    if not os.path.exists(data_file):
        print("❌ Historical data file doesn't exist!")
        print(f"   Expected: {os.path.abspath(data_file)}")
        return
    
    # Load historical data
    try:
        with open(data_file, 'r') as f:
            historical_data = json.load(f)
        print(f"✅ Loaded historical data with {len(historical_data)} entries")
    except Exception as e:
        print(f"❌ Error loading historical data: {e}")
        return
    
    # Show available dates
    available_dates = sorted(historical_data.keys())
    print(f"\n📅 Available dates in historical data:")
    print(f"   From: {available_dates[0]} to {available_dates[-1]}")
    print(f"   Recent dates: {available_dates[-5:]}")
    
    # Debug date calculations for each window
    today = datetime.now()
    print(f"\n🗓️  Current datetime: {today}")
    print(f"   Current date string: {today.strftime('%Y-%m-%d')}")
    
    # Test each lookup window
    windows = [
        ('24h', 1),
        ('7d', 7), 
        ('30d', 30)
    ]
    
    for window_name, days_ago in windows:
        print(f"\n🔍 Testing {window_name} window ({days_ago} days ago):")
        
        # Calculate target date
        target_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        print(f"   Target date: {target_date}")
        
        # Check if exact date exists
        if target_date in historical_data:
            print(f"   ✅ Exact date found in historical data")
            rates = historical_data[target_date].get('rates', {})
            print(f"   📊 Available pairs: {list(rates.keys())}")
            
            # Show sample rates
            for pair in ['NZD/USD', 'USD/BTC']:
                if pair in rates:
                    print(f"      {pair}: {rates[pair]}")
        else:
            print(f"   ❌ Exact date NOT found")
            
            # Test fallback logic
            print(f"   🔄 Testing fallback (±3 days):")
            found_fallback = False
            
            for offset in range(1, 4):  # Check 1, 2, 3 days offset
                for direction in [-1, 1]:
                    check_date = (today - timedelta(days=days_ago + (direction * offset))).strftime('%Y-%m-%d')
                    if check_date in historical_data:
                        print(f"      ✅ Found fallback: {check_date} (offset: {direction * offset} days)")
                        found_fallback = True
                        break
                if found_fallback:
                    break
            
            if not found_fallback:
                print(f"      ❌ No fallback dates found within ±3 days")
    
    # Test the actual _get_historical_rates function
    print(f"\n🧪 Testing actual _get_historical_rates function:")
    try:
        from foreign_exchange_data import _get_historical_rates
        
        for window_name, days_ago in windows:
            result = _get_historical_rates(days_ago)
            if result:
                print(f"   ✅ {window_name}: Got {len(result)} currency pairs")
                # Show sample
                for pair in ['NZD/USD', 'USD/BTC']:
                    if pair in result:
                        print(f"      {pair}: {result[pair]}")
            else:
                print(f"   ❌ {window_name}: No data returned")
                
    except Exception as e:
        print(f"   ❌ Error calling _get_historical_rates: {e}")
    
    # Test the full pipeline
    print(f"\n🔬 Testing full FX data pipeline:")
    try:
        from foreign_exchange_data import pull_fx_data
        result = pull_fx_data()
        
        if result.get('status') == 'success':
            print("✅ FX data pipeline successful")
            
            # Check which windows have data
            for pair, data in result.get('rates', {}).items():
                changes = data.get('changes', {})
                available_windows = list(changes.keys())
                print(f"   {pair}: {available_windows}")
                
                # Show the actual change values
                for window in ['24h', '7d', '30d']:
                    if window in changes:
                        print(f"      {window}: {changes[window]:+.1f}%")
        else:
            print(f"❌ FX data pipeline failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error testing FX pipeline: {e}")

if __name__ == "__main__":
    debug_fx_historical_lookup()

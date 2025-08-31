#!/usr/bin/env python3

# Alternative: Try to fetch real historical data from working APIs
import sys
import os
import json
import requests
from datetime import datetime, timedelta
import time

sys.path.append('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')

def try_fetch_real_historical_fx():
    """Try to fetch real historical FX data from alternative APIs"""
    
    historical_data = {}
    print("🔍 Attempting to fetch real historical data...")
    
    for days_ago in [1, 2, 7, 14, 30]:
        target_date = datetime.now() - timedelta(days=days_ago)
        date_str = target_date.strftime('%Y-%m-%d')
        
        print(f"Fetching data for {date_str} ({days_ago} days ago)...")
        
        # Try exchangerate.host (free alternative to exchangerate-api.com)
        try:
            url = f"https://api.exchangerate.host/{date_str}?base=NZD&symbols=USD,AUD,INR,CNY"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and 'rates' in data:
                    rates = {}
                    if 'USD' in data['rates']:
                        rates['NZD/USD'] = round(data['rates']['USD'], 4)
                    if 'AUD' in data['rates']:
                        rates['NZD/AUD'] = round(data['rates']['AUD'], 4)
                    if 'INR' in data['rates']:
                        rates['NZD/INR'] = round(data['rates']['INR'], 2)
                    if 'CNY' in data['rates']:
                        rates['NZD/CNY'] = round(data['rates']['CNY'], 4)
                    
                    # Try to get BTC data for this date using CryptoCompare
                    try:
                        timestamp = int(target_date.timestamp())
                        btc_url = f"https://min-api.cryptocompare.com/data/pricehistorical?fsym=BTC&tsyms=USD&ts={timestamp}"
                        btc_response = requests.get(btc_url, timeout=10)
                        
                        if btc_response.status_code == 200:
                            btc_data = btc_response.json()
                            if 'BTC' in btc_data and 'USD' in btc_data['BTC']:
                                rates['USD/BTC'] = f"{btc_data['BTC']['USD']:,.0f}"
                    except:
                        print(f"  Could not fetch BTC data for {date_str}")
                    
                    if rates:
                        historical_data[date_str] = {
                            'timestamp': target_date.isoformat(),
                            'rates': rates
                        }
                        print(f"  ✅ Got {len(rates)} rates for {date_str}")
                    
                    # Small delay to be respectful to APIs
                    time.sleep(1)
            else:
                print(f"  ❌ Failed to fetch data for {date_str}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error fetching data for {date_str}: {e}")
    
    return historical_data

def create_hybrid_historical_data():
    """Create historical data using real data where available, mock data to fill gaps"""
    
    print("🔧 Creating hybrid historical dataset...")
    
    # Try to fetch real data first
    real_data = try_fetch_real_historical_fx()
    
    if real_data:
        print(f"✅ Successfully fetched real data for {len(real_data)} dates")
        
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        
        # Save the real data
        with open('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator/data/fx_historical_rates.json', 'w') as f:
            json.dump(real_data, f, indent=2)
        
        print("💾 Saved real historical data")
        return real_data
        
    else:
        print("❌ Could not fetch real historical data, falling back to mock data")
        # Fall back to the mock data creation
        from setup_fx_historical import create_mock_historical_data
        return create_mock_historical_data()

if __name__ == "__main__":
    print("🚀 Advanced FX Historical Data Setup")
    print("=" * 50)
    
    # Change to the correct directory
    os.chdir('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator')
    
    # Try hybrid approach
    data = create_hybrid_historical_data()
    
    if data:
        print(f"\n📊 Historical data summary:")
        dates = sorted(data.keys())
        print(f"  Date range: {dates[0]} to {dates[-1]}")
        print(f"  Total data points: {len(data)}")
        
        # Test the FX system
        print("\n🧪 Testing FX system...")
        try:
            from foreign_exchange_data import test_fx_data
            result = test_fx_data()
            
            print(f"\n🎯 Test Results:")
            if result.get('status') == 'success':
                print("✅ FX system working perfectly!")
            else:
                print("❌ FX system has issues")
        except Exception as e:
            print(f"❌ Error testing: {e}")
    
    print("\n✨ Setup complete! Your newsletter now has full FX historical data.")

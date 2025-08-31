#!/usr/bin/env python3

# Generate 1 month of realistic FX historical data
import json
import os
from datetime import datetime, timedelta
import random

def generate_month_fx_data():
    """Generate 30 days of realistic FX historical data"""
    
    print("🚀 Generating 1 month of FX historical data...")
    
    # Starting rates (realistic as of August 2025)
    base_rates = {
        'NZD/USD': 0.589,
        'NZD/AUD': 0.901, 
        'NZD/INR': 51.9,
        'NZD/CNY': 4.2,
        'USD/BTC': 108000  # Base value for BTC
    }
    
    historical_data = {}
    
    # Generate data for the last 30 days
    for days_ago in range(30, -1, -1):  # 30 days ago to today
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime('%Y-%m-%d')
        
        # Create realistic daily variations
        # Each currency has different volatility patterns
        variations = {
            'NZD/USD': random.uniform(-0.015, 0.015),  # ±1.5% daily variation
            'NZD/AUD': random.uniform(-0.01, 0.01),    # ±1% daily variation  
            'NZD/INR': random.uniform(-0.02, 0.02),    # ±2% daily variation
            'NZD/CNY': random.uniform(-0.012, 0.012),  # ±1.2% daily variation
            'USD/BTC': random.uniform(-0.05, 0.05),    # ±5% daily variation (crypto is volatile)
        }
        
        # Add some trending behavior over the month
        trend_factor = (30 - days_ago) / 30.0  # 0 to 1 over the month
        
        trends = {
            'NZD/USD': 0.01 * trend_factor,    # Slight upward trend
            'NZD/AUD': -0.005 * trend_factor,  # Slight downward trend
            'NZD/INR': 0.015 * trend_factor,   # Upward trend
            'NZD/CNY': 0.008 * trend_factor,   # Slight upward trend
            'USD/BTC': -0.03 * trend_factor,   # Downward trend (bear market)
        }
        
        # Calculate rates for this day
        day_rates = {}
        for pair, base_rate in base_rates.items():
            # Apply daily variation + longer trend
            total_change = variations[pair] + trends[pair]
            varied_rate = base_rate * (1 + total_change)
            
            # Format according to currency pair
            if pair == 'USD/BTC':
                day_rates[pair] = f"{varied_rate:,.0f}"
            elif pair == 'NZD/INR':
                day_rates[pair] = round(varied_rate, 2)
            else:
                day_rates[pair] = round(varied_rate, 4)
        
        # Store the day's data
        historical_data[date_str] = {
            'timestamp': date.isoformat(),
            'rates': day_rates
        }
    
    # Ensure directory exists
    os.makedirs('/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator/data', exist_ok=True)
    
    # Save to JSON file
    file_path = '/Users/asif/Documents/Daily News Letter/daily-news-letter-public/src/mvp_news_aggregator/data/fx_historical_rates.json'
    with open(file_path, 'w') as f:
        json.dump(historical_data, f, indent=2)
    
    print(f"✅ Generated {len(historical_data)} days of historical data")
    
    # Show summary
    dates = sorted(historical_data.keys())
    print(f"📅 Date range: {dates[0]} to {dates[-1]}")
    
    # Show sample progression for NZD/USD
    print(f"📊 NZD/USD progression (sample):")
    sample_dates = [dates[0], dates[7], dates[14], dates[21], dates[-1]]
    for date in sample_dates:
        rate = historical_data[date]['rates']['NZD/USD']
        print(f"  {date}: {rate}")
    
    print(f"🎯 This provides data for:")
    print(f"  ✅ 1 day changes (yesterday vs today)")
    print(f"  ✅ 7 day changes (1 week ago vs today)")
    print(f"  ✅ 30 day changes (1 month ago vs today)")
    
    return historical_data

if __name__ == "__main__":
    print("📈 Smart FX Historical Data Generator")
    print("=" * 40)
    
    data = generate_month_fx_data()
    
    print(f"\n🧪 Quick test of the data:")
    
    # Test date lookups
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"Today ({today}): {'✅' if today in data else '❌'}")
    print(f"Yesterday ({yesterday}): {'✅' if yesterday in data else '❌'}")
    print(f"1 week ago ({week_ago}): {'✅' if week_ago in data else '❌'}")
    print(f"1 month ago ({month_ago}): {'✅' if month_ago in data else '❌'}")
    
    print(f"\n🎉 Ready! Now run your main pipeline:")
    print(f"cd src/mvp_news_aggregator && python main.py")

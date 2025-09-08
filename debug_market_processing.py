#!/usr/bin/env python3

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'mvp_news_aggregator'))

from market_data import get_market_changes_from_daily_data

if __name__ == "__main__":
    print("=== TESTING MARKET DATA PROCESSING ===")
    result = get_market_changes_from_daily_data()
    
    print(f"\nFinal result status: {result.get('status')}")
    if result.get('status') == 'success':
        print(f"Final result has {len(result.get('prices', {}))} instruments")
        for ticker, data in result.get('prices', {}).items():
            print(f"  {ticker}: {data.get('display_symbol')} ({data.get('category')})")
    else:
        print(f"Error: {result.get('error')}")

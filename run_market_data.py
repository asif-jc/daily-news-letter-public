#!/usr/bin/env python3

import sys
import os

# Add the src directory to Python path  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'mvp_news_aggregator'))

from market_data import pull_and_process_market_data

if __name__ == "__main__":
    result = pull_and_process_market_data()
    
    if result.get('status') == 'success':
        print(f"\n✅ Success! Got data for {len(result['prices'])} instruments:")
        for ticker, data in result['prices'].items():
            print(f"  {data['display_symbol']}: {data['current']} {data['currency']}")
    else:
        print(f"\n❌ Error: {result.get('error')}")

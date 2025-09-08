import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
try:
    import pandas as pd
except ImportError:
    pd = None

# Local storage files
DAILY_DATA_FILE = 'data/loading/market_data.json'

def _ensure_data_directory():
    """Ensure data/loading directory exists"""
    os.makedirs('data/loading', exist_ok=True)

def _calculate_percentage_change(current: float, historical: float) -> float:
    """Calculate percentage change between current and historical values"""
    if historical == 0:
        return 0.0
    return round(((current - historical) / historical) * 100, 1)

def get_market_instruments():
    """Define all market instruments with metadata"""
    return {
        # US Indices
        '^GSPC': {
            'name': 'S&P 500',
            'category': 'US Indices',
            'currency': 'USD',
            'display_symbol': 'S&P 500'
        },
        '^IXIC': {
            'name': 'NASDAQ Composite',
            'category': 'US Indices', 
            'currency': 'USD',
            'display_symbol': 'NASDAQ'
        },
        '^DJI': {
            'name': 'Dow Jones Industrial Average',
            'category': 'US Indices',
            'currency': 'USD', 
            'display_symbol': 'Dow Jones'
        },
        
        # International Indices
        '000001.SS': {
            'name': 'SSE Composite Index',
            'category': 'International Indices',
            'currency': 'CNY',
            'display_symbol': 'Shanghai (SSE)'
        },
        '^AXJO': {
            'name': 'S&P/ASX 200',
            'category': 'International Indices', 
            'currency': 'AUD',
            'display_symbol': 'ASX 200'
        },
        '^NSEI': {
            'name': 'NIFTY 50',
            'category': 'International Indices',
            'currency': 'INR', 
            'display_symbol': 'NSE (India)'
        },
        '^NZ50': {
            'name': 'S&P/NZX 50 Index',
            'category': 'International Indices',
            'currency': 'NZD',
            'display_symbol': 'NZX 50'
        },
        
        # Commodities
        'GLD': {
            'name': 'SPDR Gold Shares ETF',
            'category': 'Commodities',
            'currency': 'USD',
            'display_symbol': 'Gold (GLD)'
        },
        'USO': {
            'name': 'United States Oil Fund',
            'category': 'Commodities', 
            'currency': 'USD',
            'display_symbol': 'Oil (USO)'
        },
        'SLV': {
            'name': 'iShares Silver Trust',
            'category': 'Commodities',
            'currency': 'USD',
            'display_symbol': 'Silver (SLV)'
        },
        
        # ETFs
        'VOO': {
            'name': 'Vanguard S&P 500 ETF',
            'category': 'ETFs',
            'currency': 'USD',
            'display_symbol': 'VOO'
        },
        'VTI': {
            'name': 'Vanguard Total Stock Market ETF', 
            'category': 'ETFs',
            'currency': 'USD',
            'display_symbol': 'VTI'
        },
        'QQQ': {
            'name': 'Invesco QQQ Trust',
            'category': 'ETFs',
            'currency': 'USD',
            'display_symbol': 'QQQ'
        }
    }

def pull_market_data():
    """Pull 1 month of market data for all instruments"""
    _ensure_data_directory()
    
    instruments = get_market_instruments()
    tickers = list(instruments.keys())
    
    print(f"Fetching data for {len(tickers)} instruments...")
    
    # Get 1 month of data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    try:
        # Download data with error handling
        data = yf.download(tickers, start=start_date, end=end_date, auto_adjust=True, progress=False)
        
        if data.empty:
            return {'daily_prices': {}, 'instruments': instruments, 'fetch_timestamp': datetime.now().isoformat(), 'error': 'No data available'}
        
        # Convert to simple daily format
        daily_prices = {}
        successful_tickers = set()
        
        # For each ticker, try to extract data
        for ticker in tickers:
            try:
                # Get close prices for this ticker
                if len(tickers) == 1:
                    # Single ticker - direct column access
                    close_data = data['Close'] if 'Close' in data.columns else None
                else:
                    # Multiple tickers - try different access patterns
                    close_data = None
                    if hasattr(data.columns, 'levels'):
                        # MultiIndex columns - structure is (metric, ticker)
                        level_0_values = data.columns.get_level_values(0)  # metrics
                        level_1_values = data.columns.get_level_values(1)  # tickers
                        
                        if 'Close' in level_0_values and ticker in level_1_values:
                            close_data = data['Close'][ticker]
                    else:
                        # Sometimes yahoo returns flattened columns
                        close_col = f'{ticker}_Close' if f'{ticker}_Close' in data.columns else None
                        if close_col:
                            close_data = data[close_col]
                
                if close_data is not None:
                    valid_prices = 0
                    for date, price in close_data.items():
                        if pd.isna(price):
                            continue
                        
                        date_str = date.strftime('%Y-%m-%d')
                        if date_str not in daily_prices:
                            daily_prices[date_str] = {}
                        
                        daily_prices[date_str][ticker] = round(float(price), 2)
                        valid_prices += 1
                    
                    if valid_prices > 0:
                        successful_tickers.add(ticker)
                    
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                continue
        
        # Remove days with no data
        daily_prices = {date: prices for date, prices in daily_prices.items() if prices}
        
        failed_tickers = set(tickers) - successful_tickers
        if failed_tickers:
            print(f"Failed to get data for: {', '.join(failed_tickers)}")
        if successful_tickers:
            print(f"Successfully got data for: {', '.join(successful_tickers)}")
        
        result = {
            'daily_prices': daily_prices,
            'instruments': instruments,
            'fetch_timestamp': datetime.now().isoformat(),
            'note': 'Market data fetched from Yahoo Finance'
        }
        
        with open('data/loading/market_data.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Saved {len(daily_prices)} days of data for {len(instruments)} instruments")
        return result
        
    except Exception as e:
        print(f"Error fetching market data: {e}")
        # Return empty structure on error
        return {
            'daily_prices': {},
            'instruments': instruments,
            'fetch_timestamp': datetime.now().isoformat(),
            'error': str(e)
        }

def get_market_changes_from_daily_data() -> Dict:
    """Calculate current prices and changes from daily data"""
    try:
        print(f"\n=== MARKET DATA PROCESSING DEBUG ===")
        with open(DAILY_DATA_FILE, 'r') as f:
            daily_data = json.load(f)
        
        daily_prices = daily_data.get('daily_prices', {})
        instruments = daily_data.get('instruments', {})
        
        print(f"Loaded daily data from {DAILY_DATA_FILE}")
        print(f"Daily prices keys: {len(daily_prices)} dates")
        print(f"Instruments keys: {len(instruments)} instruments")
        print(f"Instruments: {list(instruments.keys())}")
        
        if not daily_prices:
            print("ERROR: No daily price data available")
            return {'status': 'error', 'error': 'No daily price data available'}
        
        # Get dates for comparison - find the most recent date with the most data
        dates = sorted(daily_prices.keys())
        if not dates:
            print("ERROR: No price dates available")
            return {'status': 'error', 'error': 'No price dates available'}
        
        # Find the date with the most instruments (likely the most complete trading day)
        best_date = None
        max_instruments = 0
        
        for date in dates[-7:]:  # Check last 7 dates
            instrument_count = len(daily_prices[date])
            print(f"Date {date}: {instrument_count} instruments")
            if instrument_count > max_instruments:
                max_instruments = instrument_count
                best_date = date
        
        today = best_date
        today_idx = dates.index(today)
        print(f"Using {today} as base date with {max_instruments} instruments")
        day_1_idx = max(0, today_idx - 1)
        day_7_idx = max(0, today_idx - 7)
        day_30_idx = max(0, today_idx - 30)
        
        current_prices = daily_prices[dates[today_idx]]
        prices_1d = daily_prices[dates[day_1_idx]] if day_1_idx < today_idx else {}
        prices_7d = daily_prices[dates[day_7_idx]] if day_7_idx < today_idx else {}
        prices_30d = daily_prices[dates[day_30_idx]] if day_30_idx < today_idx else {}
        
        print(f"Current prices for {today}: {len(current_prices)} instruments")
        for ticker, price in current_prices.items():
            print(f"  {ticker}: {price}")
        
        # Calculate changes
        market_data = {
            'prices': {},
            'timestamp': datetime.now().strftime('%d %b %Y, %I:%M %p'),
            'status': 'success'
        }
        
        for ticker, current_price in current_prices.items():
            print(f"\nProcessing ticker: {ticker} (price: {current_price})")
            if ticker in instruments:
                instrument_info = instruments[ticker]
                print(f"  Found instrument info - Category: {instrument_info['category']}, Symbol: {instrument_info['display_symbol']}")
                
                market_data['prices'][ticker] = {
                    'current': current_price,
                    'name': instrument_info['name'],
                    'display_symbol': instrument_info['display_symbol'],
                    'category': instrument_info['category'],
                    'currency': instrument_info['currency'],
                    'changes': {}
                }
                
                # Calculate percentage changes
                if ticker in prices_1d and prices_1d[ticker]:
                    change_1d = _calculate_percentage_change(current_price, prices_1d[ticker])
                    market_data['prices'][ticker]['changes']['24h'] = change_1d
                
                if ticker in prices_7d and prices_7d[ticker]:
                    change_7d = _calculate_percentage_change(current_price, prices_7d[ticker])
                    market_data['prices'][ticker]['changes']['7d'] = change_7d
                
                if ticker in prices_30d and prices_30d[ticker]:
                    change_30d = _calculate_percentage_change(current_price, prices_30d[ticker])
                    market_data['prices'][ticker]['changes']['30d'] = change_30d
                
                print(f"  ✅ Added {ticker} to market_data")
            else:
                print(f"  ❌ {ticker} not found in instruments definition")
        
        print(f"\nFinal market_data contains {len(market_data['prices'])} instruments")
        for ticker in market_data['prices'].keys():
            print(f"  - {ticker}")
        
        return market_data
        
    except Exception as e:
        print(f"Error calculating market changes: {e}")
        return {'status': 'error', 'error': str(e)}

def pull_and_process_market_data() -> Dict:
    """Main function - fetch fresh daily data and return current prices with changes"""
    print("Fetching fresh market data...")
    
    if pd is None:
        print("Error: pandas is required. Install with: pip install pandas")
        return {'status': 'error', 'error': 'pandas not available'}
    
    # Fetch fresh data
    pull_market_data()
    
    # Calculate and return current prices with changes
    market_data = get_market_changes_from_daily_data()
    
    if market_data.get('status') == 'success':
        print(f"Market data ready: {len(market_data['prices'])} instruments")
        return market_data
    else:
        print(f"Error processing market data: {market_data.get('error')}")
        return market_data

if __name__ == "__main__":
    result = pull_and_process_market_data()
    
    if result.get('status') == 'success':
        print("\nCurrent market data:")
        for ticker, data in result['prices'].items():
            current = data['current']
            symbol = data['display_symbol']
            currency = data['currency']
            changes = data.get('changes', {})
            
            change_str = ""
            if changes:
                change_parts = []
                for period in ['24h', '7d', '30d']:
                    if period in changes:
                        change_parts.append(f"{period}: {changes[period]:+.1f}%")
                if change_parts:
                    change_str = f" ({', '.join(change_parts)})"
            
            print(f"  {symbol}: {current} {currency}{change_str}")
    else:
        print(f"Error: {result.get('error')}")

#!/usr/bin/env python3
"""
SFC Short Position Data Fetcher
Fetches aggregated reportable short positions from SFC Hong Kong

Data Source: https://www.sfc.hk/en/Regulatory-functions/Market/Short-position-reporting/Aggregated-reportable-short-positions-of-specified-shares
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Data storage path
DATA_DIR = Path(__file__).parent / "data" / "short_positions"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SFC_INDEX_URL = "https://www.sfc.hk/en/Regulatory-functions/Market/Short-position-reporting/Aggregated-reportable-short-positions-of-specified-shares"

# Headers to avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

def get_available_csv_urls() -> list:
    """Scrape SFC page to get list of available CSV URLs"""
    import re
    try:
        response = requests.get(SFC_INDEX_URL, timeout=30, headers=HEADERS)
        if response.status_code == 200:
            # Find all CSV links - simpler pattern
            pattern = r'(https://www\.sfc\.hk/-/media/EN/pdf/spr/\d{4}/\d{2}/\d{2}/Short_Position_Reporting_Aggregated_Data_\d{8}\.csv[^\s"\'<>]*)'
            matches = re.findall(pattern, response.text)
            # Clean URLs (remove rev parameter for consistency)
            return [url.split('?')[0] for url in matches]
    except Exception as e:
        print(f"Warning: Could not fetch SFC index page: {e}")
    return []


def get_sfc_csv_url(date: datetime) -> str:
    """Generate SFC CSV URL for a given date"""
    return f"https://www.sfc.hk/-/media/EN/pdf/spr/{date.year}/{date.month:02d}/{date.day:02d}/Short_Position_Reporting_Aggregated_Data_{date.strftime('%Y%m%d')}.csv"


def fetch_short_positions(date: datetime = None) -> pd.DataFrame:
    """
    Fetch SFC short position data for a specific date.
    If no date provided, fetches the most recent available data.
    """
    if date is None:
        # Get available URLs from SFC page
        urls = get_available_csv_urls()
        if urls:
            # Try the most recent one first
            for url in urls[:5]:
                df = _try_fetch_url(url)
                if df is not None:
                    return df
        
        # Fallback: try last 14 days
        for days_back in range(14):
            check_date = datetime.now() - timedelta(days=days_back)
            df = _try_fetch_date(check_date)
            if df is not None:
                return df
        raise Exception("Could not find recent SFC short position data")
    else:
        df = _try_fetch_date(date)
        if df is None:
            raise Exception(f"No data available for {date.strftime('%Y-%m-%d')}")
        return df


def _try_fetch_url(url: str) -> pd.DataFrame:
    """Try to fetch data from a specific URL"""
    try:
        response = requests.get(url, timeout=30, allow_redirects=True, headers=HEADERS)
        if response.status_code == 200 and 'Date,Stock Code' in response.text[:100]:
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            # Extract date from URL
            import re
            match = re.search(r'(\d{8})\.csv', url)
            if match:
                df['fetch_date'] = datetime.strptime(match.group(1), '%Y%m%d').strftime('%Y-%m-%d')
            return df
    except Exception as e:
        pass
    return None


def _try_fetch_date(date: datetime) -> pd.DataFrame:
    """Try to fetch data for a specific date, return None if not available"""
    url = get_sfc_csv_url(date)
    return _try_fetch_url(url)


def get_stock_short_position(stock_code: str, df: pd.DataFrame = None) -> dict:
    """
    Get short position data for a specific stock.
    
    Args:
        stock_code: Stock code (e.g., "700" or "0700")
        df: Optional DataFrame, will fetch latest if not provided
    
    Returns:
        dict with short position info
    """
    if df is None:
        df = fetch_short_positions()
    
    # Normalize stock code (remove leading zeros for comparison)
    code_int = int(stock_code.replace('.HK', '').lstrip('0') or '0')
    
    # Find matching row
    match = df[df['Stock Code'] == code_int]
    
    if match.empty:
        return {
            'stock_code': stock_code,
            'found': False,
            'note': 'No reportable short position (below threshold or no shorts)'
        }
    
    row = match.iloc[0]
    return {
        'stock_code': stock_code,
        'found': True,
        'report_date': str(row.get('Date', row.get('fetch_date', 'unknown'))),
        'stock_name': row.get('Stock Name', 'N/A'),
        'short_shares': int(row.get('Aggregated Reportable Short Positions (Shares)', 0)),
        'short_value_hkd': int(row.get('Aggregated Reportable Short Positions (HK$)', 0)),
    }


def get_float_shares(stock_code: str) -> dict:
    """Get float shares data from Yahoo Finance"""
    try:
        import yfinance as yf
        ticker_symbol = f"{stock_code.zfill(4)}.HK"
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        return {
            'float_shares': info.get('floatShares'),
            'shares_outstanding': info.get('sharesOutstanding'),
            'market_cap': info.get('marketCap')
        }
    except Exception as e:
        return {'float_shares': None, 'shares_outstanding': None, 'market_cap': None}


def get_top_shorted_stocks(df: pd.DataFrame = None, top_n: int = 20, include_float: bool = True) -> list:
    """Get top N most shorted stocks by value, with optional float % calculation"""
    if df is None:
        df = fetch_short_positions()
    
    # Sort by short value
    value_col = 'Aggregated Reportable Short Positions (HK$)'
    sorted_df = df.sort_values(value_col, ascending=False).head(top_n)
    
    result = []
    for _, row in sorted_df.iterrows():
        stock_code = str(row['Stock Code']).zfill(4)
        short_shares = int(row.get('Aggregated Reportable Short Positions (Shares)', 0))
        
        item = {
            'stock_code': stock_code,
            'stock_name': row.get('Stock Name', 'N/A'),
            'short_shares': short_shares,
            'short_value_hkd': int(row.get('Aggregated Reportable Short Positions (HK$)', 0)),
            'short_value_billions': round(int(row.get('Aggregated Reportable Short Positions (HK$)', 0)) / 1e9, 2)
        }
        
        if include_float:
            float_data = get_float_shares(stock_code)
            if float_data['float_shares']:
                item['float_shares'] = float_data['float_shares']
                item['short_pct_of_float'] = round(short_shares / float_data['float_shares'] * 100, 2)
            if float_data['shares_outstanding']:
                item['shares_outstanding'] = float_data['shares_outstanding']
                item['short_pct_of_outstanding'] = round(short_shares / float_data['shares_outstanding'] * 100, 2)
        
        result.append(item)
    
    return result


def get_top_by_short_ratio(df: pd.DataFrame = None, top_n: int = 20) -> list:
    """Get top N stocks by short % of float (most heavily shorted relative to float)"""
    if df is None:
        df = fetch_short_positions()
    
    results = []
    shares_col = 'Aggregated Reportable Short Positions (Shares)'
    
    # Process all stocks and calculate ratios
    print("Fetching float data (this may take a moment)...")
    for _, row in df.iterrows():
        stock_code = str(row['Stock Code']).zfill(4)
        short_shares = int(row.get(shares_col, 0))
        
        if short_shares < 1000000:  # Skip very small positions
            continue
            
        float_data = get_float_shares(stock_code)
        
        if float_data['float_shares'] and float_data['float_shares'] > 0:
            pct_of_float = short_shares / float_data['float_shares'] * 100
            results.append({
                'stock_code': stock_code,
                'stock_name': row.get('Stock Name', 'N/A'),
                'short_shares': short_shares,
                'float_shares': float_data['float_shares'],
                'short_pct_of_float': round(pct_of_float, 2),
                'short_value_hkd': int(row.get('Aggregated Reportable Short Positions (HK$)', 0))
            })
    
    # Sort by short % of float
    results.sort(key=lambda x: x['short_pct_of_float'], reverse=True)
    return results[:top_n]


def save_to_json(df: pd.DataFrame, filename: str = None):
    """Save DataFrame to JSON file"""
    if filename is None:
        date_str = df['fetch_date'].iloc[0] if 'fetch_date' in df.columns else datetime.now().strftime('%Y-%m-%d')
        filename = DATA_DIR / f"sfc_short_positions_{date_str}.json"
    
    records = df.to_dict('records')
    with open(filename, 'w') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    
    return filename


def load_latest_data() -> pd.DataFrame:
    """Load most recent saved data"""
    json_files = sorted(DATA_DIR.glob("sfc_short_positions_*.json"), reverse=True)
    if not json_files:
        return fetch_short_positions()
    
    with open(json_files[0]) as f:
        data = json.load(f)
    return pd.DataFrame(data)


# CLI interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch SFC Short Position Data')
    parser.add_argument('--stock', '-s', help='Get data for specific stock code')
    parser.add_argument('--top', '-t', type=int, default=20, help='Show top N shorted stocks')
    parser.add_argument('--fetch', '-f', action='store_true', help='Fetch latest data from SFC')
    parser.add_argument('--save', action='store_true', help='Save fetched data to JSON')
    parser.add_argument('--date', '-d', help='Specific date to fetch (YYYYMMDD)')
    parser.add_argument('--by-ratio', '-r', action='store_true', help='Sort by short % of float (instead of value)')
    parser.add_argument('--no-float', action='store_true', help='Skip float data lookup (faster)')
    
    args = parser.parse_args()
    
    try:
        if args.date:
            date = datetime.strptime(args.date, '%Y%m%d')
            df = fetch_short_positions(date)
        elif args.fetch:
            print("Fetching latest SFC short position data...")
            df = fetch_short_positions()
        else:
            df = load_latest_data()
        
        if args.save:
            filepath = save_to_json(df)
            print(f"✅ Data saved to: {filepath}")
        
        if args.stock:
            result = get_stock_short_position(args.stock, df)
            # Add float data
            float_data = get_float_shares(args.stock)
            if float_data['float_shares']:
                result['float_shares'] = float_data['float_shares']
                result['short_pct_of_float'] = round(result['short_shares'] / float_data['float_shares'] * 100, 2)
            if float_data['shares_outstanding']:
                result['shares_outstanding'] = float_data['shares_outstanding']
                result['short_pct_of_outstanding'] = round(result['short_shares'] / float_data['shares_outstanding'] * 100, 2)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.by_ratio:
            print(f"\n📊 Top {args.top} Stocks by Short % of Float:\n")
            top_stocks = get_top_by_short_ratio(df, args.top)
            print(f"{'#':>2} {'Code':<6} {'Name':<20} {'Short%':>7} {'Short Shares':>15} {'Float Shares':>15}")
            print("-" * 75)
            for i, stock in enumerate(top_stocks, 1):
                print(f"{i:2}. {stock['stock_code']:<6} {stock['stock_name'][:18]:<20} {stock['short_pct_of_float']:>6.2f}% {stock['short_shares']:>14,} {stock['float_shares']:>14,}")
        else:
            include_float = not args.no_float
            print(f"\n📊 Top {args.top} Most Shorted Stocks (by value):\n")
            top_stocks = get_top_shorted_stocks(df, args.top, include_float=include_float)
            
            if include_float:
                print(f"{'#':>2} {'Code':<6} {'Name':<18} {'Value':>10} {'Short%':>7}")
                print("-" * 55)
                for i, stock in enumerate(top_stocks, 1):
                    pct = f"{stock.get('short_pct_of_float', 0):.2f}%" if stock.get('short_pct_of_float') else "N/A"
                    print(f"{i:2}. {stock['stock_code']:<6} {stock['stock_name'][:16]:<18} HK${stock['short_value_billions']:>5.1f}B {pct:>7}")
            else:
                for i, stock in enumerate(top_stocks, 1):
                    print(f"{i:2}. {stock['stock_code']} {stock['stock_name'][:20]:<20} - HK${stock['short_value_billions']}B ({stock['short_shares']:,} shares)")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

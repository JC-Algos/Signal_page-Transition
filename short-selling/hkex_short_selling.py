#!/usr/bin/env python3
"""
HKEX Daily Short Selling Turnover Scraper
Fetches daily short selling data from HKEX website

Data Source: https://www.hkex.com.hk/Market-Data/Statistics/Securities-Market/Short-Selling-Turnover-Today
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Data storage path
DATA_DIR = Path(__file__).parent / "data" / "hkex_short_selling"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HKEX_URL = "https://www.hkex.com.hk/Market-Data/Statistics/Securities-Market/Short-Selling-Turnover-Today?sc_lang=en"

HKEX_MAIN_BOARD_URL = "https://www.hkex.com.hk/Market-Data/Statistics/Securities-Market/Short-Selling-Turnover-Today/Short-Selling-Turnover-(Main-Board)-up-to-day-close-today?sc_lang=en"

def fetch_short_selling_data() -> pd.DataFrame:
    """
    Fetch daily short selling turnover data from HKEX using Playwright
    Returns DataFrame with stock-level short selling data
    """
    from playwright.sync_api import sync_playwright
    import re
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Loading HKEX short selling page...")
        page.goto(HKEX_MAIN_BOARD_URL, wait_until='networkidle', timeout=60000)
        
        # Wait for data to load
        page.wait_for_timeout(5000)
        
        # Get visible text which contains the data
        visible_text = page.evaluate('() => document.body.innerText')
        
        browser.close()
        
        # Parse the text format data
        # Format: CODE   NAME OF STOCK               (SH)            ($)
        #         1  CKH HOLDINGS           1,520,500    100,518,925
        
        data = []
        lines = visible_text.split('\n')
        
        # Find the trading date
        trading_date = None
        for line in lines:
            if 'TRADING DATE' in line:
                match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})', line)
                if match:
                    trading_date = match.group(1)
                break
        
        # Parse stock data
        # Pattern: number, name, shares (with commas), value (with commas)
        pattern = re.compile(r'^\s*(\d+)\s+([A-Z][A-Z0-9\s\-&\'\.]+?)\s+([\d,]+)\s+([\d,]+)\s*$')
        
        for line in lines:
            match = pattern.match(line)
            if match:
                code = match.group(1).zfill(4)
                name = match.group(2).strip()
                shares = int(match.group(3).replace(',', ''))
                value = int(match.group(4).replace(',', ''))
                
                data.append({
                    'stock_code': code,
                    'stock_name': name,
                    'short_turnover_shares': shares,
                    'short_turnover_hkd': value,
                    'trading_date': trading_date
                })
        
        if data:
            df = pd.DataFrame(data)
            print(f"Parsed {len(df)} stocks from HKEX")
            return df
        else:
            print("No data parsed from page")
            return pd.DataFrame()


def fetch_with_api() -> dict:
    """
    Try to fetch data via HKEX API endpoints
    """
    import requests
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }
    
    # Try various HKEX API endpoints
    endpoints = [
        "https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Securities-Market/Short-Selling",
        "https://www.hkex.com.hk/api/Market-Data/Statistics/Securities-Market/Short-Selling",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json() if 'json' in response.headers.get('Content-Type', '') else {'html': response.text[:1000]}
        except:
            continue
    
    return {}


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


def save_data(df: pd.DataFrame, date: str = None):
    """Save data to JSON file"""
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    filepath = DATA_DIR / f"hkex_short_selling_{date}.json"
    df.to_json(filepath, orient='records', indent=2)
    return filepath


def load_latest_data() -> pd.DataFrame:
    """Load most recent saved data"""
    json_files = sorted(DATA_DIR.glob("hkex_short_selling_*.json"), reverse=True)
    if not json_files:
        return fetch_short_selling_data()
    
    return pd.read_json(json_files[0])


# Alternative: Parse HKEX fixed-format reports
def fetch_hkex_report_txt():
    """
    HKEX publishes short selling in fixed-format text files
    Try to find and parse these
    """
    import requests
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    today = datetime.now()
    date_str = today.strftime('%y%m%d')
    
    # Try different URL patterns
    urls = [
        f"https://www.hkex.com.hk/eng/stat/smstat/ssturnover/ncms/SSTS_{date_str}.txt",
        f"https://www.hkex.com.hk/-/media/HKEX-Market/Market-Data/Statistics/Securities-Market/Short-Selling/ssts{date_str}.txt",
    ]
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200 and len(response.text) > 100:
                return parse_hkex_txt(response.text)
        except:
            continue
    
    return pd.DataFrame()


def parse_hkex_txt(text: str) -> pd.DataFrame:
    """Parse HKEX fixed-format text file"""
    lines = text.strip().split('\n')
    data = []
    
    for line in lines:
        # Parse based on fixed column positions
        # Typical format: StockCode  Name  ShortTurnover  TotalTurnover  %
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            data.append({
                'stock_code': parts[0],
                'short_turnover': parts[-3] if len(parts) > 3 else None,
                'total_turnover': parts[-2] if len(parts) > 2 else None,
                'short_ratio': parts[-1] if len(parts) > 1 else None
            })
    
    return pd.DataFrame(data)


def add_float_data(df: pd.DataFrame, top_n: int = None) -> pd.DataFrame:
    """Add float share data and calculate short % of float"""
    if top_n:
        df = df.nlargest(top_n, 'short_turnover_hkd')
    
    result = []
    for _, row in df.iterrows():
        stock_code = row['stock_code']
        float_data = get_float_shares(stock_code)
        
        item = row.to_dict()
        if float_data['float_shares']:
            item['float_shares'] = float_data['float_shares']
            # Note: This is daily TURNOVER as % of float, not position
            item['daily_turnover_pct_of_float'] = round(row['short_turnover_shares'] / float_data['float_shares'] * 100, 4)
        if float_data['shares_outstanding']:
            item['shares_outstanding'] = float_data['shares_outstanding']
        
        result.append(item)
    
    return pd.DataFrame(result)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch HKEX Short Selling Data')
    parser.add_argument('--fetch', '-f', action='store_true', help='Fetch latest data')
    parser.add_argument('--save', action='store_true', help='Save data to file')
    parser.add_argument('--top', '-t', type=int, default=20, help='Show top N stocks')
    parser.add_argument('--with-float', action='store_true', help='Add float share data')
    parser.add_argument('--stock', '-s', help='Get data for specific stock code')
    
    args = parser.parse_args()
    
    try:
        if args.fetch:
            print("Fetching HKEX short selling data...")
            df = fetch_short_selling_data()
            
            if df.empty:
                print("Trying alternative text format...")
                df = fetch_hkex_report_txt()
        else:
            df = load_latest_data()
        
        if not df.empty:
            if args.stock:
                # Filter for specific stock
                code = args.stock.zfill(4)
                stock_df = df[df['stock_code'] == code]
                if not stock_df.empty:
                    stock_data = stock_df.iloc[0].to_dict()
                    float_data = get_float_shares(code)
                    stock_data.update(float_data)
                    if float_data['float_shares']:
                        stock_data['daily_turnover_pct_of_float'] = round(
                            stock_data['short_turnover_shares'] / float_data['float_shares'] * 100, 4
                        )
                    print(json.dumps(stock_data, indent=2, ensure_ascii=False, default=str))
                else:
                    print(f"Stock {code} not found in today's short selling data")
            else:
                # Show top N
                top_df = df.nlargest(args.top, 'short_turnover_hkd')
                
                if args.with_float:
                    print("Adding float data (this takes a moment)...")
                    top_df = add_float_data(top_df)
                    print(f"\n📊 Top {args.top} Short Selling Turnover (with float %):\n")
                    print(f"{'#':>2} {'Code':<6} {'Name':<18} {'Turnover':>12} {'% Float':>8}")
                    print("-" * 55)
                    for i, (_, row) in enumerate(top_df.iterrows(), 1):
                        pct = f"{row.get('daily_turnover_pct_of_float', 0):.3f}%" if row.get('daily_turnover_pct_of_float') else "N/A"
                        turnover = row['short_turnover_hkd'] / 1e6
                        print(f"{i:2}. {row['stock_code']:<6} {row['stock_name'][:16]:<18} HK${turnover:>8.1f}M {pct:>8}")
                else:
                    print(f"\n📊 Top {args.top} Short Selling Turnover:\n")
                    print(f"{'#':>2} {'Code':<6} {'Name':<20} {'Shares':>14} {'Value (HK$)':>14}")
                    print("-" * 65)
                    for i, (_, row) in enumerate(top_df.iterrows(), 1):
                        print(f"{i:2}. {row['stock_code']:<6} {row['stock_name'][:18]:<20} {row['short_turnover_shares']:>13,} {row['short_turnover_hkd']:>13,}")
            
            if args.save and not args.stock:
                filepath = save_data(df)
                print(f"\n✅ Saved to: {filepath}")
        else:
            print("❌ No data found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

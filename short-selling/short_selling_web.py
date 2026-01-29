#!/usr/bin/env python3
"""
JC Algos Short Selling Web Tool API
Flask API for short selling data and charts
"""

from flask import Flask, jsonify, request, send_from_directory, make_response
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Import local modules
from sfc_short_positions import fetch_short_positions, get_stock_short_position, get_float_shares
from hkex_short_selling import fetch_short_selling_data, load_latest_data as load_hkex_latest
from stock_names import get_chinese_name

app = Flask(__name__, static_folder='static')

# CORS headers for cross-origin requests
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,OPTIONS')
    return response

# Data directories
DATA_DIR = Path(__file__).parent / "data"
SFC_DATA_DIR = DATA_DIR / "short_positions"
HKEX_DATA_DIR = DATA_DIR / "hkex_short_selling"


def get_historical_sfc_data(stock_code: str, weeks: int = 14) -> list:
    """Get historical SFC short position data for a stock"""
    code = str(stock_code).zfill(4)
    code_int = int(code)
    
    results = []
    json_files = sorted(SFC_DATA_DIR.glob("sfc_short_positions_*.json"), reverse=True)
    
    cutoff_date = datetime.now() - timedelta(weeks=weeks)
    
    for filepath in json_files[:70]:  # Check last 70 files (covers 10 weeks)
        try:
            # Extract date from filename
            date_str = filepath.stem.replace("sfc_short_positions_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            
            if file_date < cutoff_date:
                continue
            
            with open(filepath) as f:
                data = json.load(f)
            
            df = pd.DataFrame(data)
            match = df[df['Stock Code'] == code_int]
            
            if not match.empty:
                row = match.iloc[0]
                short_shares = int(row.get('Aggregated Reportable Short Positions (Shares)', 0))
                short_value = int(row.get('Aggregated Reportable Short Positions (HK$)', 0))
                
                # Get float for %
                float_data = get_float_shares(code)
                pct = round(short_shares / float_data['float_shares'] * 100, 2) if float_data.get('float_shares') else None
                
                results.append({
                    'date': date_str,
                    'short_shares': short_shares,
                    'short_value': short_value,
                    'pct_of_float': pct
                })
        except Exception as e:
            continue
    
    return sorted(results, key=lambda x: x['date'])


def get_historical_hkex_data(stock_code: str, days: int = 10) -> list:
    """Get historical HKEX daily short selling data for a stock"""
    code = str(stock_code).zfill(4)
    
    results = []
    json_files = sorted(HKEX_DATA_DIR.glob("hkex_short_selling_*.json"), reverse=True)
    
    for filepath in json_files[:days]:
        try:
            date_str = filepath.stem.replace("hkex_short_selling_", "")
            
            with open(filepath) as f:
                data = json.load(f)
            
            df = pd.DataFrame(data)
            match = df[df['stock_code'] == code]
            
            if not match.empty:
                row = match.iloc[0]
                short_shares = int(row.get('short_turnover_shares', 0))
                short_value = int(row.get('short_turnover_hkd', 0))
                
                # Get float for %
                float_data = get_float_shares(code)
                pct = round(short_shares / float_data['float_shares'] * 100, 4) if float_data.get('float_shares') else None
                
                results.append({
                    'date': date_str,
                    'short_shares': short_shares,
                    'short_value': short_value,
                    'pct_of_float': pct
                })
        except Exception as e:
            continue
    
    return sorted(results, key=lambda x: x['date'])


@app.route('/')
def index():
    """Serve the main page"""
    static_path = Path(__file__).parent / 'static'
    return send_from_directory(static_path, 'short_selling.html')


@app.route('/api/short/lookup')
def lookup_stock():
    """Look up short selling data for a specific stock"""
    ticker = request.args.get('ticker', '').strip()
    if not ticker:
        return jsonify({'error': 'Missing ticker parameter'}), 400
    
    # Normalize ticker
    code = ticker.replace('.HK', '').lstrip('0').zfill(4)
    
    try:
        # Get Chinese name
        chinese_name = get_chinese_name(code)
        
        # Get current SFC aggregate position
        sfc_df = fetch_short_positions()
        sfc_data = get_stock_short_position(code, sfc_df)
        
        # Get today's HKEX daily short
        try:
            hkex_df = fetch_short_selling_data()
            hkex_match = hkex_df[hkex_df['stock_code'] == code]
            if not hkex_match.empty:
                row = hkex_match.iloc[0]
                daily_data = {
                    'found': True,
                    'short_shares': int(row['short_turnover_shares']),
                    'short_value': int(row['short_turnover_hkd']),
                    'trading_date': row.get('trading_date', 'Today')
                }
            else:
                daily_data = {'found': False, 'note': 'No short selling today'}
        except:
            daily_data = {'found': False, 'note': 'Daily data not available'}
        
        # Get float data
        float_data = get_float_shares(code)
        
        # Calculate percentages
        if float_data.get('float_shares'):
            if sfc_data.get('found') and sfc_data.get('short_shares'):
                sfc_data['pct_of_float'] = round(sfc_data['short_shares'] / float_data['float_shares'] * 100, 2)
            if daily_data.get('found') and daily_data.get('short_shares'):
                daily_data['pct_of_float'] = round(daily_data['short_shares'] / float_data['float_shares'] * 100, 4)
        
        # Get historical data for chart (14 weeks = 1 quarter)
        historical_sfc = get_historical_sfc_data(code, weeks=14)
        historical_hkex = get_historical_hkex_data(code, days=10)
        
        return jsonify({
            'stock_code': code,
            'chinese_name': chinese_name,
            'aggregate': sfc_data,
            'daily': daily_data,
            'float_shares': float_data.get('float_shares'),
            'historical_aggregate': historical_sfc,
            'historical_daily': historical_hkex
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/short/top20')
def get_top20():
    """Get top 20 short selling stocks for both daily and aggregate"""
    try:
        from short_selling_report import generate_telegram_report_v2
        from sfc_short_positions import get_top_shorted_stocks
        from hkex_short_selling import add_float_data
        import math
        
        # Get SFC aggregate top 20 by % of float
        sfc_df = fetch_short_positions()
        report_date = sfc_df['fetch_date'].iloc[0] if 'fetch_date' in sfc_df.columns else datetime.now().strftime('%Y-%m-%d')
        
        top_by_value = get_top_shorted_stocks(sfc_df, 50, include_float=True)
        aggregate_top = sorted(
            [s for s in top_by_value if s.get('short_pct_of_float', 0) > 0],
            key=lambda x: x.get('short_pct_of_float', 0),
            reverse=True
        )[:20]
        
        # Add Chinese names
        for stock in aggregate_top:
            stock['chinese_name'] = get_chinese_name(stock['stock_code'])
        
        # Get HKEX daily top 20 by % of float
        hkex_df = fetch_short_selling_data()
        trading_date = hkex_df['trading_date'].iloc[0] if 'trading_date' in hkex_df.columns else "Today"
        
        top_by_value_hkex = hkex_df.nlargest(50, 'short_turnover_hkd')
        top_df = add_float_data(top_by_value_hkex)
        
        valid_rows = []
        for _, row in top_df.iterrows():
            pct = row.get('daily_turnover_pct_of_float', 0)
            if pct and not math.isnan(pct) and pct > 0:
                valid_rows.append({
                    'stock_code': row['stock_code'],
                    'stock_name': row['stock_name'],
                    'chinese_name': get_chinese_name(row['stock_code']),
                    'short_shares': int(row['short_turnover_shares']),
                    'short_value': int(row['short_turnover_hkd']),
                    'pct_of_float': round(pct, 4)
                })
        
        daily_top = sorted(valid_rows, key=lambda x: x['pct_of_float'], reverse=True)[:20]
        
        return jsonify({
            'aggregate': {
                'report_date': report_date,
                'stocks': aggregate_top
            },
            'daily': {
                'trading_date': trading_date,
                'stocks': daily_top
            }
        })
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


if __name__ == '__main__':
    # Ensure static directory exists
    static_dir = Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)
    
    app.run(host='0.0.0.0', port=5004, debug=True)

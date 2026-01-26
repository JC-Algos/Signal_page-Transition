"""
JC Algos Signal - Backend API
Flask-based REST API for trading signal analysis
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import asyncio
import yfinance as yf
import os
import json
import sqlite3
from functools import wraps

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Configuration
API_ID = "25298694"
API_HASH = "1a23ce55412c2ac111b6cef8ec5ad4b2"
CHAT_ID = -1002288872733
SESSION_STRING = "1BVtsOK0Bu1mdLw0ZmAxuH6sGLHMBocWd9Dw2W3I3Rja9D6BgfFBPzszTRfPDMHkmeH_ALMu45ldFHffHzP6XajwjeRFTILWcp1YvtILT951EUe05U6XQIC03QTUxl1P51JnVPwp1GOOmCB_XCmREBtyQ4KgCYH0pJz5fAuBYfim-L86kEk-MwFNxbl1iCZfjW9z6k1Zx7wUyv92mieG-vOlvpNi6jaZoZ3OaP2H5PvOjLsxuIlSp8OM2Eba-bGZTEPO0GhXNmRnS_pi3ueko0wkQZYlCh0zNZ9KreQlBaZcDPoW7P-UoOzxLAS68Q91C-KBD7r-pTefJpBfhahDdR2mQEryEQds="

# Approved emails
APPROVED_EMAILS = [
    "jcstai@gmail.com", "walter@rocim.com", "jshek.tavolo@gmail.com",
    "cupid.chu@gmail.com", "jeff.lau@artecapital.com", "kevin.kwanhh@gmail.com",
    "reeve3487@gmail.com", "wongsjl138@gmail.com", "jasonckb@yahoo.com.hk",
    "tsetim.hk@gmail.com", "patten", "stephensum0915@gmail.com",
    "Kennethlee1115@gmail.com"
]

# Exchange mapping
EXCHANGES = {
    "Hong Kong": "HKEX",
    "US": "BATS",
    "Shanghai": "SSE_DLY",
    "Shenzhen": "ZSE_DLY",
    "Forex": "OANDA",
    "HSI": "HSI"
}

# Database setup
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'signals.db')

def init_db():
    """Initialize SQLite database"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            exchange TEXT,
            buy_signals INTEGER,
            valid_buy_signals INTEGER,
            sell_signals INTEGER,
            valid_sell_signals INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, exchange)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Helper functions
def extract_value(text, pattern):
    """Extract value using regex"""
    if not isinstance(text, str):
        return ""
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return ""

def format_number(value):
    """Format numbers to 4 decimal places"""
    try:
        if value is None or value == "" or pd.isna(value):
            return ""
        return "{:.4f}".format(float(value))
    except (ValueError, TypeError):
        return ""

def clean_ticker_for_yf(ticker, exchange):
    """Format ticker symbols for Yahoo Finance"""
    if ticker.endswith(','):
        ticker = ticker[:-1]
    
    if exchange == "HKEX":
        if ticker.startswith('HKG:'):
            ticker_number = ticker[4:]
        else:
            ticker_number = ticker
        ticker_number = ''.join(filter(str.isdigit, ticker_number))
        ticker_number = ticker_number.zfill(4)
        ticker = f"{ticker_number}.HK"
    
    return ticker

def format_ticker_for_display(ticker, exchange):
    """Format ticker for display"""
    if ticker.endswith(','):
        ticker = ticker[:-1]
    if exchange == "HKEX" and not ticker.startswith('HKG:'):
        ticker = f"HKG:{ticker}"
    return ticker

def determine_valid_signal(sentiment, trigger_price_str, trigger_day_close_str, strategy=""):
    """Determine if a signal is valid"""
    if not sentiment or not trigger_price_str or not trigger_day_close_str:
        return "No"
    
    try:
        trigger_price = float(trigger_price_str) if trigger_price_str else None
        trigger_day_close = float(trigger_day_close_str) if trigger_day_close_str else None
        
        if trigger_price is None or trigger_day_close is None:
            return "No"
        
        is_magic = ("Magic 9" in strategy or "Magic 13" in strategy) if strategy else False
        
        if sentiment == "好":
            if is_magic:
                return "Yes" if trigger_day_close <= trigger_price else "No"
            else:
                return "Yes" if trigger_day_close >= trigger_price else "No"
        elif sentiment == "淡":
            if is_magic:
                return "Yes" if trigger_day_close >= trigger_price else "No"
            else:
                return "Yes" if trigger_day_close <= trigger_price else "No"
        else:
            return "No"
    except (ValueError, TypeError):
        return "No"

def process_message(message_text):
    """Process a single Telegram message"""
    msg = message_text.strip()
    data = {}
    exchanges = ["HKEX", "BATS", "OANDA", "SSE_DLY", "HSI", "ZSE_DLY"]
    
    for exchange in exchanges:
        data[exchange] = ""
    
    data["策略失效價"] = ""
    data["日期"] = ""
    data["備注"] = ""
    data["完整訊息"] = msg
    
    lines = msg.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        for exchange in exchanges:
            if exchange in line and ":" in line:
                try:
                    ticker_info = line.split(":")[1].strip()
                    data[exchange] = ticker_info
                except:
                    data[exchange] = line
        
        if "日期" in line and "=" in line:
            try:
                date_value = line.split("=")[1].strip()
                data["日期"] = date_value
            except:
                data["日期"] = line
        
        if "策略失效價" in line:
            data["策略失效價"] = line
        
        if "備注" in line or "備註" in line:
            data["備注"] = line
    
    return data

def get_stock_data(tickers):
    """Get stock data from Yahoo Finance"""
    all_data = {}
    if not tickers:
        return all_data
    
    try:
        data = yf.download(tickers, period="1mo", group_by='ticker', progress=False)
        
        if isinstance(data, pd.DataFrame):
            if 'Close' in data.columns:
                all_data[tickers[0]] = data
            elif isinstance(data.columns, pd.MultiIndex):
                for ticker in tickers:
                    if ticker in data.columns.levels[0]:
                        ticker_data = data[ticker].copy()
                        all_data[ticker] = ticker_data
    except Exception as e:
        print(f"Error fetching stock data: {str(e)}")
    
    return all_data

async def fetch_telegram_data_async(days_ago, from_date=None, to_date=None):
    """Fetch data from Telegram asynchronously"""
    if from_date and to_date:
        pass
    else:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_ago)
    
    column_names = [
        "Message_ID", "Message_Date", "Message_Time", "BATS", "HKEX", 
        "OANDA", "SSE_DLY", "HSI", "ZSE_DLY", "策略失效價", "日期", "備注", "完整訊息"
    ]
    
    all_data = {col: [] for col in column_names}
    
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, 0, "Not authorized"
        
        msg_count = 0
        
        async for message in client.iter_messages(CHAT_ID, limit=1000, offset_date=None):
            msg_date = message.date.replace(tzinfo=None)
            from_date_tz = from_date.replace(tzinfo=None) if hasattr(from_date, 'tzinfo') else from_date
            to_date_tz = to_date.replace(tzinfo=None) if hasattr(to_date, 'tzinfo') else to_date
            
            if msg_date < from_date_tz:
                continue
            if msg_date > to_date_tz:
                continue
            
            if message.text is not None:
                data = process_message(message.text)
                data["Message_ID"] = str(message.id)
                data["Message_Date"] = message.date.strftime("%Y-%m-%d")
                data["Message_Time"] = message.date.strftime("%H:%M:%S")
                
                for col in column_names:
                    if col in data:
                        all_data[col].append(data[col])
                    else:
                        all_data[col].append("")
                
                msg_count += 1
        
        await client.disconnect()
        
        df = pd.DataFrame(all_data)
        return df, msg_count, None
        
    except Exception as e:
        return None, 0, str(e)

def process_signal_data(df, exchange_filter):
    """Process signal data from raw dataframe"""
    result = []
    
    if df is None or len(df) == 0:
        return result
    
    lookup_tickers = []
    temp_data = []
    
    for _, row in df.iterrows():
        if exchange_filter not in row or row[exchange_filter] == "":
            continue
        
        ticker_match = re.search(r'^([^\s]+)', row[exchange_filter])
        if not ticker_match:
            continue
        
        ticker = ticker_match.group(1)
        display_ticker = format_ticker_for_display(ticker, exchange_filter)
        lookup_ticker = clean_ticker_for_yf(ticker, exchange_filter)
        
        trigger_price = extract_value(row[exchange_filter], r'信號觸發價\s*=\s*([0-9.]+)')
        stop_price = extract_value(row['策略失效價'], r'策略失效價\s*=\s*([0-9.]+)')
        sentiment = extract_value(row['完整訊息'], r'看([好淡])')
        resistance1 = extract_value(row['完整訊息'], r'阻力\s*1\s*=\s*([0-9.]+)')
        resistance2 = extract_value(row['完整訊息'], r'阻力\s*2\s*=\s*([0-9.]+)')
        resistance3 = extract_value(row['完整訊息'], r'阻力\s*3\s*=\s*([0-9.]+)')
        
        strategy_match = re.search(r'^(.*?)看', row['完整訊息'])
        strategy = strategy_match.group(1).strip() if strategy_match else ""
        
        msg_date = row['Message_Date'] if 'Message_Date' in row else ""
        
        lookup_tickers.append(lookup_ticker)
        temp_data.append({
            'display_ticker': display_ticker,
            'lookup_ticker': lookup_ticker,
            'signal_date': msg_date,
            'sentiment': sentiment,
            'trigger_price': trigger_price,
            'stop_price': stop_price,
            'resistance1': resistance1,
            'resistance2': resistance2,
            'resistance3': resistance3,
            'date': msg_date,
            'strategy': strategy
        })
    
    # Get stock data
    all_stock_data = get_stock_data(lookup_tickers)
    
    for item in temp_data:
        lookup_ticker = item['lookup_ticker']
        display_ticker = item['display_ticker']
        signal_date_str = item['signal_date']
        
        trigger_close = None
        current_price = None
        
        if lookup_ticker in all_stock_data:
            stock_df = all_stock_data[lookup_ticker]
            
            try:
                signal_date = pd.to_datetime(signal_date_str)
                valid_dates = stock_df.index[stock_df.index >= signal_date]
                if len(valid_dates) > 0:
                    closest_date = valid_dates[0]
                    trigger_close = stock_df.loc[closest_date, 'Close']
                else:
                    trigger_close = stock_df['Close'].iloc[-1]
            except:
                pass
            
            try:
                if not stock_df.empty:
                    current_price = stock_df['Close'].iloc[-1]
            except:
                pass
        
        formatted_trigger_close = format_number(trigger_close)
        is_valid = determine_valid_signal(item['sentiment'], item['trigger_price'], formatted_trigger_close, item['strategy'])
        
        # Calculate P/L
        pl_percent = None
        try:
            signal_trigger_price = float(item['trigger_price']) if item['trigger_price'] else None
            if signal_trigger_price and current_price:
                if item['sentiment'] == "好":
                    pl_percent = ((current_price / signal_trigger_price) - 1) * 100
                elif item['sentiment'] == "淡":
                    pl_percent = ((signal_trigger_price / current_price) - 1) * 100
        except:
            pass
        
        if is_valid == "No":
            pl_percent = None
        
        result.append({
            'ticker_symbol': display_ticker,
            'sentiment': item['sentiment'],
            'trigger_price': format_number(item['trigger_price']),
            'stop_price': format_number(item['stop_price']),
            'resistance1': format_number(item['resistance1']),
            'resistance2': format_number(item['resistance2']),
            'resistance3': format_number(item['resistance3']),
            'date': item['date'],
            'strategy': item['strategy'],
            'trigger_day_close': formatted_trigger_close,
            'present_close': format_number(current_price),
            'pl_percent': format_number(pl_percent),
            'valid_signal': is_valid
        })
    
    return result

# API Routes
@app.route('/')
def serve_index():
    """Serve the main page"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate user by email"""
    data = request.json
    email = data.get('email', '').lower().strip()
    
    if email in [e.lower().strip() for e in APPROVED_EMAILS]:
        # Generate simple token (in production, use JWT)
        import hashlib
        token = hashlib.sha256(f"{email}{datetime.now().isoformat()}".encode()).hexdigest()
        
        return jsonify({
            'success': True,
            'token': token,
            'email': email
        })
    
    return jsonify({
        'success': False,
        'error': 'Email not authorized. Please visit: https://www.patreon.com/c/JC_Algo'
    }), 401

@app.route('/api/exchanges', methods=['GET'])
def get_exchanges():
    """Get available exchanges"""
    return jsonify(EXCHANGES)

@app.route('/api/signals/fetch', methods=['POST'])
def fetch_signals():
    """Fetch signals from Telegram"""
    data = request.json
    exchange = data.get('exchange', 'HKEX')
    days_ago = data.get('days_ago', 1)
    from_date = data.get('from_date')
    to_date = data.get('to_date')
    
    # Parse dates if provided
    if from_date and to_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
        to_date = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    else:
        from_date = None
        to_date = None
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        df, msg_count, error = loop.run_until_complete(
            fetch_telegram_data_async(days_ago, from_date, to_date)
        )
    finally:
        loop.close()
    
    if error:
        return jsonify({'success': False, 'error': error}), 500
    
    if df is None or len(df) == 0:
        return jsonify({
            'success': True,
            'signals': [],
            'statistics': {},
            'message': 'No signals found for the specified date range'
        })
    
    # Process signals
    signals = process_signal_data(df, exchange)
    
    # Calculate statistics
    buy_signals = len([s for s in signals if s['sentiment'] == '好'])
    sell_signals = len([s for s in signals if s['sentiment'] == '淡'])
    valid_buy = len([s for s in signals if s['sentiment'] == '好' and s['valid_signal'] == 'Yes'])
    valid_sell = len([s for s in signals if s['sentiment'] == '淡' and s['valid_signal'] == 'Yes'])
    
    statistics = {
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'valid_buy_signals': valid_buy,
        'valid_sell_signals': valid_sell,
        'bullish_pct': round((valid_buy / buy_signals) * 100, 1) if buy_signals > 0 else 0,
        'bearish_pct': round((valid_sell / sell_signals) * 100, 1) if sell_signals > 0 else 0
    }
    
    # Save to history
    if signals:
        date_str = signals[0]['date'] if signals[0]['date'] else datetime.now().strftime('%Y-%m-%d')
        save_signal_history(date_str, exchange, statistics)
    
    return jsonify({
        'success': True,
        'signals': signals,
        'statistics': statistics,
        'total_messages': msg_count
    })

@app.route('/api/signals/history/<exchange>', methods=['GET'])
def get_signal_history(exchange):
    """Get signal history for an exchange"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT date, buy_signals, valid_buy_signals, sell_signals, valid_sell_signals
        FROM signal_history
        WHERE exchange = ?
        ORDER BY date DESC
        LIMIT 30
    ''', (exchange,))
    
    rows = c.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        buy = row[1]
        valid_buy = row[2]
        sell = row[3]
        valid_sell = row[4]
        
        history.append({
            'date': row[0],
            'buy_signals': buy,
            'valid_buy_signals': valid_buy,
            'sell_signals': sell,
            'valid_sell_signals': valid_sell,
            'initial_ratio': f"{buy} 好 : {sell} 淡",
            'actual_ratio': f"{valid_buy} 好 : {valid_sell} 淡",
            'bullish_strength': f"{buy} 好 : {valid_buy} 有效 ({round((valid_buy/buy)*100, 1) if buy > 0 else 0}%)",
            'bearish_strength': f"{sell} 淡 : {valid_sell} 有效 ({round((valid_sell/sell)*100, 1) if sell > 0 else 0}%)"
        })
    
    return jsonify({'success': True, 'history': history})

def save_signal_history(date_str, exchange, stats):
    """Save signal statistics to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        INSERT OR REPLACE INTO signal_history 
        (date, exchange, buy_signals, valid_buy_signals, sell_signals, valid_sell_signals)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        date_str, exchange, 
        stats['buy_signals'], stats['valid_buy_signals'],
        stats['sell_signals'], stats['valid_sell_signals']
    ))
    
    conn.commit()
    conn.close()

@app.route('/api/signals/export', methods=['POST'])
def export_signals():
    """Export signals as CSV"""
    data = request.json
    signals = data.get('signals', [])
    
    if not signals:
        return jsonify({'success': False, 'error': 'No signals to export'}), 400
    
    df = pd.DataFrame(signals)
    csv_data = df.to_csv(index=False)
    
    return jsonify({
        'success': True,
        'csv': csv_data,
        'filename': f"signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')

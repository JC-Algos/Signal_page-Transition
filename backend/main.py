"""
JC Algos Signal API - Backend
FastAPI server for Telegram signal processing
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import asyncio
import os
import json
import yfinance as yf
from telethon import TelegramClient
from telethon.sessions import StringSession

# ============================================
# CONFIGURATION
# ============================================

API_ID = "25298694"
API_HASH = "1a23ce55412c2ac111b6cef8ec5ad4b2"
CHAT_ID = -1002288872733
SESSION_STRING = "1BVtsOK0Bu1mdLw0ZmAxuH6sGLHMBocWd9Dw2W3I3Rja9D6BgfFBPzszTRfPDMHkmeH_ALMu45ldFHffHzP6XajwjeRFTILWcp1YvtILT951EUe05U6XQIC03QTUxl1P51JnVPwp1GOOmCB_XCmREBtyQ4KgCYH0pJz5fAuBYfim-L86kEk-MwFNxbl1iCZfjW9z6k1Zx7wUyv92mieG-vOlvpNi6jaZoZ3OaP2H5PvOjLsxuIlSp8OM2Eba-bGZTEPO0GhXNmRnS_pi3ueko0wkQZYlCh0zNZ9KreQlBaZcDPoW7P-UoOzxLAS68Q91C-KBD7r-pTefJpBfhahDdR2mQEryEQds="

# Create stats directory
os.makedirs('stats', exist_ok=True)

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="JC Algos Signal API",
    description="API for fetching and processing Telegram trading signals",
    version="1.0.0"
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# PYDANTIC MODELS
# ============================================

class SignalResponse(BaseModel):
    ticker_symbol: str
    sentiment: str  # 好 or 淡
    trigger_price: str
    stop_price: str
    resistance_1: str
    resistance_2: str
    resistance_3: str
    date: str
    strategy: str
    trigger_day_close: str
    present_close: str
    pl_percent: str
    valid_signal: str

class SignalStats(BaseModel):
    date: str
    buy_signals: int
    valid_buy_signals: int
    sell_signals: int
    valid_sell_signals: int
    initial_momentum_ratio: str
    actual_momentum_ratio: str
    bullish_strength: str
    bearish_strength: str

class SignalsResultResponse(BaseModel):
    success: bool
    message: str
    total_signals: int
    buy_signals: int
    sell_signals: int
    valid_buy_signals: int
    valid_sell_signals: int
    closest_date: Optional[str]
    signals: List[dict]

class HistoryResponse(BaseModel):
    success: bool
    exchange: str
    total_records: int
    history: List[dict]

class BuildHistoryRequest(BaseModel):
    exchange: str
    days: int = 14

# ============================================
# HELPER FUNCTIONS
# ============================================

def extract_value(text, pattern):
    """Extract value using regex pattern"""
    if not isinstance(text, str):
        return ""
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return ""


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


def clean_ticker_for_yf(ticker, exchange):
    """Format ticker for Yahoo Finance"""
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


def format_number(value):
    """Format number to 4 decimal places"""
    try:
        if value is None or value == "" or pd.isna(value):
            return ""
        return "{:.4f}".format(float(value))
    except (ValueError, TypeError):
        return ""


def determine_valid_signal(sentiment, trigger_price_str, trigger_day_close_str, strategy=""):
    """Determine if signal is valid"""
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


def process_signal_data(df, exchange_filter):
    """Process signal data from raw dataframe"""
    results = []
    
    if df is None or len(df) == 0:
        return results
    
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
            'resistance_1': resistance1,
            'resistance_2': resistance2,
            'resistance_3': resistance3,
            'date': msg_date,
            'strategy': strategy
        })
    
    # Get stock data
    all_stock_data = get_stock_data(lookup_tickers)
    
    for item in temp_data:
        lookup_ticker = item.pop('lookup_ticker')
        display_ticker = item.pop('display_ticker')
        signal_date_str = item.pop('signal_date')
        
        trigger_price = None
        current_price = None
        
        if lookup_ticker in all_stock_data:
            stock_df = all_stock_data[lookup_ticker]
            
            try:
                signal_date = pd.to_datetime(signal_date_str)
                valid_dates = stock_df.index[stock_df.index >= signal_date]
                if len(valid_dates) > 0:
                    closest_date = valid_dates[0]
                    trigger_price = stock_df.loc[closest_date, 'Close']
                else:
                    trigger_price = stock_df['Close'].iloc[-1]
            except:
                pass
            
            try:
                if not stock_df.empty:
                    current_price = stock_df['Close'].iloc[-1]
            except:
                pass
        
        formatted_trigger_price = format_number(trigger_price)
        is_valid = determine_valid_signal(item['sentiment'], item['trigger_price'], formatted_trigger_price, item['strategy'])
        
        pl_percent = None
        try:
            if item['trigger_price'] and item['trigger_price'] != "":
                signal_trigger_price = float(item['trigger_price'])
                
                if signal_trigger_price is not None and current_price is not None:
                    if item['sentiment'] == "好":
                        pl_percent = ((current_price / signal_trigger_price) - 1) * 100
                    elif item['sentiment'] == "淡":
                        pl_percent = ((signal_trigger_price / current_price) - 1) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            pl_percent = None
        
        if is_valid == "No":
            pl_percent = None
        
        results.append({
            'ticker_symbol': display_ticker,
            'sentiment': item['sentiment'],
            'trigger_price': format_number(item['trigger_price']),
            'stop_price': format_number(item['stop_price']),
            'resistance_1': format_number(item['resistance_1']),
            'resistance_2': format_number(item['resistance_2']),
            'resistance_3': format_number(item['resistance_3']),
            'date': item['date'],
            'strategy': item['strategy'],
            'trigger_day_close': formatted_trigger_price,
            'present_close': format_number(current_price),
            'pl_percent': format_number(pl_percent),
            'valid_signal': is_valid
        })
    
    return results


async def fetch_telegram_data(days_ago, custom_from_date=None, custom_to_date=None):
    """Fetch data from Telegram"""
    if custom_from_date is not None and custom_to_date is not None:
        from_date = custom_from_date
        to_date = custom_to_date
    else:
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_ago)
    
    column_names = [
        "Message_ID", "Message_Date", "Message_Time", "BATS", "HKEX", "OANDA",
        "SSE_DLY", "HSI", "ZSE_DLY", "策略失效價", "日期", "備注", "完整訊息"
    ]
    
    all_data = {col: [] for col in column_names}
    
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, 0
        
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
        return df, msg_count
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return None, 0


def save_signal_stats(date_str, buy_signals, valid_buy_signals, sell_signals, valid_sell_signals, exchange):
    """Save signal statistics to CSV"""
    stats_data = {
        'date': date_str,
        'buy_signals': buy_signals,
        'valid_buy_signals': valid_buy_signals,
        'sell_signals': sell_signals,
        'valid_sell_signals': valid_sell_signals,
        'initial_momentum_ratio': f"{buy_signals} 好 : {sell_signals} 淡",
        'actual_momentum_ratio': f"{valid_buy_signals} 好 : {valid_sell_signals} 淡",
        'bullish_strength': f"{buy_signals} 好 : {valid_buy_signals} 有效好 ({round((valid_buy_signals / buy_signals) * 100, 1) if buy_signals > 0 else 0}%)",
        'bearish_strength': f"{sell_signals} 淡 : {valid_sell_signals} 有效淡 ({round((valid_sell_signals / sell_signals) * 100, 1) if sell_signals > 0 else 0}%)"
    }
    
    csv_path = f'stats/{exchange}_signal_history.csv'
    
    # Load existing data
    if os.path.exists(csv_path):
        existing_df = pd.read_csv(csv_path)
        existing_data = existing_df.to_dict('records')
    else:
        existing_data = []
    
    # Check for existing entry
    existing_idx = None
    for i, entry in enumerate(existing_data):
        if entry['date'] == date_str:
            existing_idx = i
            break
    
    if existing_idx is not None:
        existing_data[existing_idx] = stats_data
    else:
        existing_data.append(stats_data)
    
    # Sort by date
    existing_data.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=True)
    
    # Save to CSV
    save_df = pd.DataFrame(existing_data)
    save_df.to_csv(csv_path, index=False)
    
    return existing_data


def load_signal_history(exchange, from_date=None, to_date=None):
    """Load signal history from CSV with optional date range filter"""
    csv_path = f'stats/{exchange}_signal_history.csv'
    
    if not os.path.exists(csv_path):
        return []
    
    try:
        history_df = pd.read_csv(csv_path)
        
        # Apply date range filter if provided
        if from_date or to_date:
            history_df['date_parsed'] = pd.to_datetime(history_df['date'])
            
            if from_date:
                from_dt = datetime.strptime(from_date, '%Y-%m-%d')
                history_df = history_df[history_df['date_parsed'] >= from_dt]
            
            if to_date:
                to_dt = datetime.strptime(to_date, '%Y-%m-%d')
                history_df = history_df[history_df['date_parsed'] <= to_dt]
            
            history_df = history_df.drop('date_parsed', axis=1)
        
        return history_df.to_dict('records')
    except Exception as e:
        print(f"Error loading history: {str(e)}")
        return []


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "JC Algos Signal API",
        "version": "1.0.0",
        "endpoints": {
            "/api/signals": "GET - Fetch trading signals",
            "/api/history/{exchange}": "GET - Get signal history",
            "/api/build-history": "POST - Build signal history for multiple dates"
        }
    }


@app.get("/api/signals", response_model=SignalsResultResponse)
async def get_signals(
    exchange: str = Query("HKEX", description="Exchange filter: HKEX, BATS, SSE_DLY, ZSE_DLY, OANDA"),
    days: int = Query(1, description="Number of days to look back", ge=1, le=30),
    from_date: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="To date (YYYY-MM-DD)"),
    sort_by_sentiment: bool = Query(True, description="Sort by sentiment (好 first)"),
    sort_by_pl: bool = Query(False, description="Sort by P/L"),
    pl_order: str = Query("desc", description="P/L sort order: asc or desc")
):
    """Fetch and process trading signals from Telegram"""
    try:
        # Parse dates
        custom_from = None
        custom_to = None
        
        if from_date and to_date:
            custom_from = datetime.strptime(from_date, '%Y-%m-%d')
            custom_to = datetime.combine(
                datetime.strptime(to_date, '%Y-%m-%d').date(),
                datetime.max.time()
            )
        
        # Fetch from Telegram
        df, msg_count = await fetch_telegram_data(days, custom_from, custom_to)
        
        if df is None or len(df) == 0:
            return SignalsResultResponse(
                success=False,
                message="No messages found for the specified date range",
                total_signals=0,
                buy_signals=0,
                sell_signals=0,
                valid_buy_signals=0,
                valid_sell_signals=0,
                closest_date=None,
                signals=[]
            )
        
        # Process signals
        signals = process_signal_data(df, exchange)
        
        if not signals:
            return SignalsResultResponse(
                success=False,
                message=f"No signals found for {exchange}",
                total_signals=0,
                buy_signals=0,
                sell_signals=0,
                valid_buy_signals=0,
                valid_sell_signals=0,
                closest_date=None,
                signals=[]
            )
        
        # Convert to DataFrame for sorting
        result_df = pd.DataFrame(signals)
        
        # Apply sorting
        if sort_by_sentiment or sort_by_pl:
            result_df['pl_numeric'] = pd.to_numeric(result_df['pl_percent'], errors='coerce')
            
            if sort_by_sentiment and sort_by_pl:
                ascending_pl = pl_order == "asc"
                result_df = result_df.sort_values(
                    ['sentiment', 'pl_numeric'],
                    ascending=[True, ascending_pl],
                    na_position='last'
                )
            elif sort_by_sentiment:
                result_df = result_df.sort_values('sentiment', ascending=True)
            elif sort_by_pl:
                ascending_pl = pl_order == "asc"
                result_df = result_df.sort_values('pl_numeric', ascending=ascending_pl, na_position='last')
            
            result_df = result_df.drop('pl_numeric', axis=1)
        
        signals = result_df.to_dict('records')
        
        # Calculate statistics
        buy_signals = len([s for s in signals if s['sentiment'] == '好'])
        sell_signals = len([s for s in signals if s['sentiment'] == '淡'])
        valid_buy_signals = len([s for s in signals if s['sentiment'] == '好' and s['valid_signal'] == 'Yes'])
        valid_sell_signals = len([s for s in signals if s['sentiment'] == '淡' and s['valid_signal'] == 'Yes'])
        
        # Find closest date
        closest_date = None
        today = datetime.now().date()
        min_days_diff = float('inf')
        
        for signal in signals:
            try:
                date_obj = pd.to_datetime(signal['date']).date()
                days_diff = abs((date_obj - today).days)
                if days_diff < min_days_diff:
                    min_days_diff = days_diff
                    closest_date = date_obj.strftime('%Y-%m-%d')
            except:
                pass
        
        # Save statistics
        if closest_date:
            save_signal_stats(
                date_str=closest_date,
                buy_signals=buy_signals,
                valid_buy_signals=valid_buy_signals,
                sell_signals=sell_signals,
                valid_sell_signals=valid_sell_signals,
                exchange=exchange
            )
        
        return SignalsResultResponse(
            success=True,
            message=f"Found {len(signals)} signals",
            total_signals=len(signals),
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            valid_buy_signals=valid_buy_signals,
            valid_sell_signals=valid_sell_signals,
            closest_date=closest_date,
            signals=signals
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history/{exchange}", response_model=HistoryResponse)
async def get_history(
    exchange: str,
    from_date: Optional[str] = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="To date (YYYY-MM-DD)")
):
    """Get signal history for an exchange with optional date range filter"""
    try:
        history = load_signal_history(exchange, from_date, to_date)
        
        return HistoryResponse(
            success=True,
            exchange=exchange,
            total_records=len(history),
            history=history
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/build-history")
async def build_history(request: BuildHistoryRequest):
    """Build signal history for multiple dates"""
    try:
        exchange = request.exchange
        days = request.days
        
        dates_processed = []
        errors = []
        
        for i in range(days):
            date_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            from_date = datetime.strptime(date_str, '%Y-%m-%d')
            to_date = from_date + timedelta(days=1) - timedelta(seconds=1)
            
            try:
                df, _ = await fetch_telegram_data(1, from_date, to_date)
                
                if df is not None and len(df) > 0:
                    signals = process_signal_data(df, exchange)
                    
                    if signals:
                        buy_signals = len([s for s in signals if s['sentiment'] == '好'])
                        sell_signals = len([s for s in signals if s['sentiment'] == '淡'])
                        valid_buy_signals = len([s for s in signals if s['sentiment'] == '好' and s['valid_signal'] == 'Yes'])
                        valid_sell_signals = len([s for s in signals if s['sentiment'] == '淡' and s['valid_signal'] == 'Yes'])
                        
                        save_signal_stats(
                            date_str=date_str,
                            buy_signals=buy_signals,
                            valid_buy_signals=valid_buy_signals,
                            sell_signals=sell_signals,
                            valid_sell_signals=valid_sell_signals,
                            exchange=exchange
                        )
                        
                        dates_processed.append(date_str)
            
            except Exception as e:
                errors.append({"date": date_str, "error": str(e)})
        
        return {
            "success": True,
            "message": f"History building complete for {exchange}",
            "dates_processed": len(dates_processed),
            "dates": dates_processed,
            "errors": errors
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/exchanges")
async def get_exchanges():
    """Get list of available exchanges"""
    return {
        "exchanges": [
            {"code": "HKEX", "name": "Hong Kong"},
            {"code": "BATS", "name": "US"}
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

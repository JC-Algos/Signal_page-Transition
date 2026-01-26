import streamlit as st
from telethon import TelegramClient
from telethon.sessions import StringSession
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
import asyncio
import nest_asyncio
import yfinance as yf
import time
import os
import json

# Apply nest_asyncio to allow running asyncio in Streamlit
nest_asyncio.apply()

# Configure page
st.set_page_config(page_title="Telegram Signals", layout="wide")

# ============================================
# HEADER WITH HOME BUTTON
# ============================================
def render_header():
    st.markdown("""
    <style>
    .header-container {
        background-color: #2d2d2d;
        padding: 10px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: -1rem -1rem 1rem -1rem;
    }
    .header-title {
        color: white;
        font-size: 1.4rem;
        font-weight: bold;
        margin: 0;
    }
    .header-btn {
        background-color: #f0f0f0;
        color: #333;
        padding: 8px 16px;
        border: none;
        border-radius: 4px;
        text-decoration: none;
        font-size: 0.9rem;
    }
    .header-btn:hover {
        background-color: #e0e0e0;
    }
    </style>
    <div class="header-container">
        <h1 class="header-title">Telegram JC Algos Signal</h1>
        <a href="index.html" class="header-btn">🏠 回首頁</a>
    </div>
    """, unsafe_allow_html=True)

# Render the header
render_header()

# Telegram API credentials
API_ID = "25298694"
API_HASH = "1a23ce55412c2ac111b6cef8ec5ad4b2"
CHAT_ID = -1002288872733

# Hardcoded session string
SESSION_STRING = "1BVtsOK0Bu1mdLw0ZmAxuH6sGLHMBocWd9Dw2W3I3Rja9D6BgfFBPzszTRfPDMHkmeH_ALMu45ldFHffHzP6XajwjeRFTILWcp1YvtILT951EUe05U6XQIC03QTUxl1P51JnVPwp1GOOmCB_XCmREBtyQ4KgCYH0pJz5fAuBYfim-L86kEk-MwFNxbl1iCZfjW9z6k1Zx7wUyv92mieG-vOlvpNi6jaZoZ3OaP2H5PvOjLsxuIlSp8OM2Eba-bGZTEPO0GhXNmRnS_pi3ueko0wkQZYlCh0zNZ9KreQlBaZcDPoW7P-UoOzxLAS68Q91C-KBD7r-pTefJpBfhahDdR2mQEryEQds="

# Initialize session state for signal history
if 'signal_history' not in st.session_state:
    st.session_state.signal_history = {}

# ============================================
# SIGNAL HISTORY FUNCTIONS
# ============================================

def save_signal_stats(date_str, buy_signals, valid_buy_signals, sell_signals, valid_sell_signals, exchange):
    """
    Save day-by-day signal statistics to session state and CSV for historical tracking
    """
    # Prepare data to save
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

    # Initialize exchange history if not exists
    if exchange not in st.session_state.signal_history:
        st.session_state.signal_history[exchange] = []

    # Check if an entry for this date exists
    existing_idx = None
    for i, entry in enumerate(st.session_state.signal_history[exchange]):
        if entry['date'] == date_str:
            existing_idx = i
            break

    # Add or update the entry
    if existing_idx is not None:
        # Update existing entry
        st.session_state.signal_history[exchange][existing_idx] = stats_data
    else:
        # Add new entry
        st.session_state.signal_history[exchange].append(stats_data)

    # Sort by date (newest first)
    st.session_state.signal_history[exchange].sort(
        key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'),
        reverse=True
    )

    # Save to CSV for persistence
    try:
        # Create a new dataframe for saving
        save_df = pd.DataFrame(st.session_state.signal_history[exchange])

        # Create stats directory if it doesn't exist
        os.makedirs('stats', exist_ok=True)

        # Save to CSV - this will create a new file or overwrite the existing one
        save_df.to_csv(f'stats/{exchange}_signal_history.csv', index=False)
    except Exception as e:
        st.warning(f"Could not save history to file: {str(e)}")

    return st.session_state.signal_history[exchange]


def load_signal_history(exchange):
    """
    Load day-by-day signal history from session state or CSV file
    """
    # If already in session state, return it
    if exchange in st.session_state.signal_history and len(st.session_state.signal_history[exchange]) > 0:
        return st.session_state.signal_history[exchange]

    # Try to load from CSV
    try:
        csv_path = f'stats/{exchange}_signal_history.csv'
        if os.path.exists(csv_path):
            # Read the CSV file
            history_df = pd.read_csv(csv_path)

            # Convert to list of dictionaries
            history = history_df.to_dict('records')

            # Store in session state
            st.session_state.signal_history[exchange] = history

            return history
    except Exception as e:
        st.warning(f"Error loading signal history: {str(e)}")

    # If we can't load from file, initialize empty
    st.session_state.signal_history[exchange] = []
    return []


def display_signal_history_table(exchange):
    """
    Display day-by-day signal history table
    """
    # Load the history data
    history = load_signal_history(exchange)

    if not history:
        st.info(f"No historical data found for {exchange}. Data will be saved as you analyze different dates.")
        return

    # Define column names for display
    col_names = {
        'date': '日期',
        'buy_signals': '買入信號數量',
        'valid_buy_signals': '有效買入信號',
        'sell_signals': '賣出信號數量',
        'valid_sell_signals': '有效賣出信號',
        'initial_momentum_ratio': '初始動量比率',
        'actual_momentum_ratio': '實際動量比率',
        'bullish_strength': '看好動量強度',
        'bearish_strength': '看淡動量強度'
    }

    # Create a DataFrame for display
    df = pd.DataFrame(history)

    # Ensure all columns exist
    for col in col_names.keys():
        if col not in df.columns:
            df[col] = ""

    # Select and rename columns
    df = df[list(col_names.keys())]
    df.columns = [col_names[col] for col in df.columns]

    # Display the table
    st.subheader(f"{exchange} 信號歷史統計")

    # Add index column for row numbers
    df = df.reset_index(drop=True)

    # Apply alternating row styling
    if not df.empty:
        # Create styled dataframe
        styled_df = df.style.apply(
            lambda _: ['background-color: #f5f5f5' if i % 2 == 0 else 'background-color: white' for i in range(len(df))],
            axis=0
        )
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)

    # Add download button
    if not df.empty:
        csv = df.to_csv(index=False)
        st.download_button(
            label=f"下載 {exchange} 信號歷史數據",
            data=csv,
            file_name=f"{exchange}_signal_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )


# ============================================
# MESSAGE PROCESSING FUNCTIONS
# ============================================

def extract_value(text, pattern):
    """Function to extract values using regex"""
    if not isinstance(text, str):
        return ""
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return ""


def process_message(message_text):
    """Process a single message from Telegram"""
    # Strip message to get only the data
    msg = message_text.strip()

    # Initialize data dictionary
    data = {}

    # Define possible exchanges
    exchanges = ["HKEX", "BATS", "OANDA", "SSE_DLY", "HSI", "ZSE_DLY"]

    # Initialize exchange columns
    for exchange in exchanges:
        data[exchange] = ""

    # Add additional columns for common data
    data["策略失效價"] = ""
    data["日期"] = ""
    data["備注"] = ""
    data["完整訊息"] = msg

    # Split message into lines
    lines = msg.split('\n')

    # Extract message information
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for exchanges in the line
        for exchange in exchanges:
            if exchange in line and ":" in line:
                # Extract ticker and price
                try:
                    ticker_info = line.split(":")[1].strip()
                    data[exchange] = ticker_info
                except:
                    data[exchange] = line

        # Check for date
        if "日期" in line and "=" in line:
            try:
                date_value = line.split("=")[1].strip()
                data["日期"] = date_value
            except:
                data["日期"] = line

        # Check for risk management
        if "策略失效價" in line:
            data["策略失效價"] = line

        # Check for notes
        if "備注" in line or "備註" in line:
            data["備注"] = line

    return data


# ============================================
# TICKER FORMATTING FUNCTIONS
# ============================================

def clean_ticker_for_yf(ticker, exchange):
    """
    Format ticker symbols properly for Yahoo Finance
    For Hong Kong stocks, ensure the code is padded to 4 digits before .HK
    """
    # Remove comma suffix
    if ticker.endswith(','):
        ticker = ticker[:-1]

    # Format for Yahoo Finance
    if exchange == "HKEX":
        # Extract the numeric part if it starts with HKG:
        if ticker.startswith('HKG:'):
            ticker_number = ticker[4:]
        else:
            ticker_number = ticker

        # Remove any non-numeric characters
        ticker_number = ''.join(filter(str.isdigit, ticker_number))

        # Pad to 4 digits
        ticker_number = ticker_number.zfill(4)

        # Add .HK suffix
        ticker = f"{ticker_number}.HK"

    return ticker


def format_ticker_for_display(ticker, exchange):
    """Format ticker for display"""
    # Remove comma suffix
    if ticker.endswith(','):
        ticker = ticker[:-1]

    # For display, use HKG: prefix for HKEX tickers
    if exchange == "HKEX" and not ticker.startswith('HKG:'):
        ticker = f"HKG:{ticker}"

    return ticker


# ============================================
# STOCK DATA FUNCTIONS
# ============================================

def get_stock_data(tickers):
    """
    Get both current and historical stock data for a list of tickers
    Returns a dictionary with the ticker as key and a dataframe of data as value
    """
    all_data = {}

    if not tickers:
        return all_data

    # Get data for all tickers - for both current and historical info
    # Using period=1mo to ensure we have enough historical data
    try:
        data = yf.download(tickers, period="1mo", group_by='ticker', progress=False)

        # Process based on structure
        if isinstance(data, pd.DataFrame):
            # Single ticker case
            if 'Close' in data.columns:
                all_data[tickers[0]] = data
            # Multiple ticker case with nested MultiIndex
            elif isinstance(data.columns, pd.MultiIndex):
                for ticker in tickers:
                    if ticker in data.columns.levels[0]:
                        ticker_data = data[ticker].copy()
                        all_data[ticker] = ticker_data
    except Exception as e:
        st.warning(f"Error fetching stock data: {str(e)}")

    return all_data


def format_number(value):
    """Format numbers to 4 decimal places"""
    try:
        if value is None or value == "" or pd.isna(value):
            return ""
        return "{:.4f}".format(float(value))
    except (ValueError, TypeError):
        return ""


# ============================================
# SIGNAL VALIDATION FUNCTIONS
# ============================================

def determine_valid_signal(sentiment, trigger_price_str, trigger_day_close_str, strategy=""):
    """
    Determine if a signal is valid based on the sentiment and price comparison.
    Standard logic:
        好: Valid if trigger day's close >= trigger price
        淡: Valid if trigger day's close <= trigger price
    Special case for "Magic 9" and "Magic 13" strategies:
        好: Valid if trigger day's close <= trigger price (reversed logic)
        淡: Valid if trigger day's close >= trigger price (reversed logic)
    """
    # If any of the values are missing, return "No"
    if not sentiment or not trigger_price_str or not trigger_day_close_str:
        return "No"

    try:
        # Convert prices to float for comparison
        trigger_price = float(trigger_price_str) if trigger_price_str else None
        trigger_day_close = float(trigger_day_close_str) if trigger_day_close_str else None

        # Skip validation if any value is missing
        if trigger_price is None or trigger_day_close is None:
            return "No"

        # Check if this is a Magic 9 or Magic 13 strategy - FIXED to include both
        is_magic = ("Magic 9" in strategy or "Magic 13" in strategy) if strategy else False

        # Check validity based on sentiment and strategy
        if sentiment == "好":
            if is_magic:
                # Reversed logic for Magic 9/13 strategy
                return "Yes" if trigger_day_close <= trigger_price else "No"
            else:
                # Standard logic
                return "Yes" if trigger_day_close >= trigger_price else "No"
        elif sentiment == "淡":
            if is_magic:
                # Reversed logic for Magic 9/13 strategy
                return "Yes" if trigger_day_close >= trigger_price else "No"
            else:
                # Standard logic
                return "Yes" if trigger_day_close <= trigger_price else "No"
        else:
            return "No"
    except (ValueError, TypeError):
        # If conversion fails, return "No"
        return "No"


# ============================================
# DATA PROCESSING FUNCTION
# ============================================

def process_signal_data(df, exchange_filter):
    """Process signal data from raw dataframe"""
    result_df = pd.DataFrame({
        'ticker_symbol': [],
        '看好看淡': [],
        '信號觸發價': [],
        '策略失效價': [],
        '阻力 1': [],
        '阻力 2': [],
        '阻力 3': [],
        '日期': [],
        '策略': [],
        'Trigger Day\'s Close': [],
        'Present Close': [],
        '% P/L': [],
        'Valid Signal?': []
    })

    if df is None or len(df) == 0:
        return result_df

    # Lists to collect ticker information
    lookup_tickers = []
    display_tickers = []
    signal_dates = []

    # First pass: extract base data
    temp_data = []

    for _, row in df.iterrows():
        if exchange_filter not in row or row[exchange_filter] == "":
            continue

        # Extract ticker
        ticker_match = re.search(r'^([^\s]+)', row[exchange_filter])
        if not ticker_match:
            continue

        ticker = ticker_match.group(1)

        # Create display and lookup versions
        display_ticker = format_ticker_for_display(ticker, exchange_filter)
        lookup_ticker = clean_ticker_for_yf(ticker, exchange_filter)

        # Extract other fields
        trigger_price = extract_value(row[exchange_filter], r'信號觸發價\s*=\s*([0-9.]+)')
        stop_price = extract_value(row['策略失效價'], r'策略失效價\s*=\s*([0-9.]+)')
        sentiment = extract_value(row['完整訊息'], r'看([好淡])')
        resistance1 = extract_value(row['完整訊息'], r'阻力\s*1\s*=\s*([0-9.]+)')
        resistance2 = extract_value(row['完整訊息'], r'阻力\s*2\s*=\s*([0-9.]+)')
        resistance3 = extract_value(row['完整訊息'], r'阻力\s*3\s*=\s*([0-9.]+)')

        strategy_match = re.search(r'^(.*?)看', row['完整訊息'])
        strategy = strategy_match.group(1).strip() if strategy_match else ""

        # Get date
        msg_date = row['Message_Date'] if 'Message_Date' in row else ""

        # Store data
        lookup_tickers.append(lookup_ticker)
        display_tickers.append(display_ticker)
        signal_dates.append(msg_date)

        temp_data.append({
            'display_ticker': display_ticker,
            'lookup_ticker': lookup_ticker,
            'signal_date': msg_date,
            '看好看淡': sentiment,
            '信號觸發價': trigger_price,
            '策略失效價': stop_price,
            '阻力 1': resistance1,
            '阻力 2': resistance2,
            '阻力 3': resistance3,
            '日期': msg_date,
            '策略': strategy
        })

    # Get all stock data at once
    with st.spinner("Fetching stock data..."):
        all_stock_data = get_stock_data(lookup_tickers)

    # Debug message for number of tickers with data
    st.info(f"Successfully fetched data for {len(all_stock_data)} out of {len(lookup_tickers)} tickers.")

    # Process each ticker with price data
    for item in temp_data:
        lookup_ticker = item.pop('lookup_ticker')
        display_ticker = item.pop('display_ticker')
        signal_date_str = item.pop('signal_date')

        # Default values
        trigger_price = None
        current_price = None

        # Process price data if available
        if lookup_ticker in all_stock_data:
            stock_df = all_stock_data[lookup_ticker]

            # Get trigger day price (closest to signal date)
            try:
                signal_date = pd.to_datetime(signal_date_str)
                # Find closest date on or after signal date
                valid_dates = stock_df.index[stock_df.index >= signal_date]
                if len(valid_dates) > 0:
                    closest_date = valid_dates[0]
                    trigger_price = stock_df.loc[closest_date, 'Close']
                else:
                    # If no dates on or after signal, use last available price
                    trigger_price = stock_df['Close'].iloc[-1]
            except Exception as e:
                pass

            # Get current price (most recent)
            try:
                if not stock_df.empty:
                    current_price = stock_df['Close'].iloc[-1]
            except Exception as e:
                pass

        # Format trigger price for validation
        formatted_trigger_price = format_number(trigger_price)

        # Determine if signal is valid - pass the strategy to handle Magic 9/13 special case
        is_valid = determine_valid_signal(item['看好看淡'], item['信號觸發價'], formatted_trigger_price, item['策略'])

        # Calculate P/L using UNIVERSAL FORMULAS - FIXED VERSION
        pl_percent = None
        signal_trigger_price = None

        try:
            # Convert signal trigger price to float
            if item['信號觸發價'] and item['信號觸發價'] != "":
                signal_trigger_price = float(item['信號觸發價'])

            # Calculate P/L using universal formulas regardless of strategy
            if signal_trigger_price is not None and current_price is not None:
                if item['看好看淡'] == "好":
                    # Universal formula for bullish signals: P/L = (現價/觸發價) - 1
                    pl_percent = ((current_price / signal_trigger_price) - 1) * 100
                elif item['看好看淡'] == "淡":
                    # Universal formula for bearish signals: P/L = (觸發價/現價) - 1
                    pl_percent = ((signal_trigger_price / current_price) - 1) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            pl_percent = None

        # If signal is invalid, clear P/L
        if is_valid == "No":
            pl_percent = None

        # Format numbers to 4 decimal places
        item['信號觸發價'] = format_number(item['信號觸發價'])
        item['策略失效價'] = format_number(item['策略失效價'])
        item['阻力 1'] = format_number(item['阻力 1'])
        item['阻力 2'] = format_number(item['阻力 2'])
        item['阻力 3'] = format_number(item['阻力 3'])

        # Add remaining data
        item['ticker_symbol'] = display_ticker
        item['Trigger Day\'s Close'] = formatted_trigger_price
        item['Present Close'] = format_number(current_price)
        item['% P/L'] = format_number(pl_percent)
        item['Valid Signal?'] = is_valid

        # Add to result dataframe
        result_df = pd.concat([result_df, pd.DataFrame([item])], ignore_index=True)

    return result_df


# ============================================
# TELEGRAM DATA FETCHING
# ============================================

async def fetch_telegram_data(days_ago, custom_from_date=None, custom_to_date=None):
    """
    Fetch data from Telegram within the specified date range
    Parameters:
        days_ago (int): Number of days to look back (used if custom_from_date and custom_to_date are None)
        custom_from_date (datetime, optional): Start date for fetching data
        custom_to_date (datetime, optional): End date for fetching data
    """
    # Set date range based on input parameters
    if custom_from_date is not None and custom_to_date is not None:
        from_date = custom_from_date
        to_date = custom_to_date
    else:
        to_date = datetime.now()  # Use datetime.now() instead of datetime.today() for better precision
        from_date = to_date - timedelta(days=days_ago)

    # Define column structure
    column_names = [
        "Message_ID", "Message_Date", "Message_Time", "BATS", "HKEX", "OANDA",
        "SSE_DLY", "HSI", "ZSE_DLY", "策略失效價", "日期", "備注", "完整訊息"
    ]

    # Dictionary to store columns of data
    all_data = {col: [] for col in column_names}

    status_placeholder = st.empty()
    status_placeholder.info("Connecting to Telegram...")

    # Add debug information
    debug_expander = st.expander("Debug Information (Click to expand)")
    with debug_expander:
        st.write(f"Current time: {datetime.now()} (local)")
        st.write(f"Looking for messages from: {from_date} to {to_date}")
        if custom_from_date is not None:
            st.write(f"Using custom date range: {custom_from_date.strftime('%Y-%m-%d')} to {custom_to_date.strftime('%Y-%m-%d')}")

    # Create client with StringSession
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

        # Connect to client
        await client.connect()

        # Check if we're authorized
        if not await client.is_user_authorized():
            status_placeholder.error("Not authorized with Telegram. The session string may be invalid or expired.")
            await client.disconnect()
            return None, 0

        status_placeholder.info(f"Fetching messages from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}...")

        # Process each message
        msg_count = 0

        # Get messages - IMPORTANT CHANGE: Use a None for offset_date to get the most recent messages
        # instead of filtering by to_date.date(), which might be excluding today's messages
        with debug_expander:
            st.write("Starting to fetch messages (most recent first)...")

        async for message in client.iter_messages(CHAT_ID, limit=1000, offset_date=None):
            # Debug message date
            with debug_expander:
                st.write(f"Message date: {message.date} | Message ID: {message.id}")

            # Check if message date is within our range - use replace(tzinfo=None) for consistent comparison
            msg_date = message.date.replace(tzinfo=None)
            from_date_tz = from_date.replace(tzinfo=None) if hasattr(from_date, 'tzinfo') else from_date
            to_date_tz = to_date.replace(tzinfo=None) if hasattr(to_date, 'tzinfo') else to_date

            # Debug date comparison
            with debug_expander:
                st.write(f"Comparing: {msg_date} >= {from_date_tz} and {msg_date} <= {to_date_tz}")

            if msg_date < from_date_tz:
                with debug_expander:
                    st.write(f"Skipping message from {message.date} - before {from_date}")
                continue

            if msg_date > to_date_tz:
                with debug_expander:
                    st.write(f"Skipping message from {message.date} - after {to_date}")
                continue

            if message.text is not None:
                # Process message
                data = process_message(message.text)

                # Add message metadata
                data["Message_ID"] = str(message.id)
                data["Message_Date"] = message.date.strftime("%Y-%m-%d")
                data["Message_Time"] = message.date.strftime("%H:%M:%S")

                # Add data to columns
                for col in column_names:
                    if col in data:
                        all_data[col].append(data[col])
                    else:
                        all_data[col].append("")

                msg_count += 1

                if msg_count % 10 == 0:
                    status_placeholder.info(f"Processed {msg_count} messages...")

                # Debug
                with debug_expander:
                    st.write(f"Processed message: {message.date}")

        # Create DataFrame
        df = pd.DataFrame(all_data)

        # Show raw messages for debugging
        if not df.empty:
            with debug_expander:
                st.subheader("Raw Message Data (First 10 messages)")
                st.dataframe(df[["Message_ID", "Message_Date", "Message_Time", "完整訊息"]].head(10))

        # Disconnect
        await client.disconnect()

        status_placeholder.success(f"Finished processing {msg_count} messages")

        # If no data for today, find most recent data
        if df.empty:
            status_placeholder.info("No messages found for the specified date range. Attempting to fetch most recent data...")

            # Re-connect
            await client.connect()

            # Get more messages going further back
            additional_days = 30  # Look back up to 30 days
            new_from_date = datetime.now() - timedelta(days=additional_days)

            # Dictionary to store columns of data
            all_data = {col: [] for col in column_names}
            msg_count = 0

            # Get messages - use None for offset_date to get most recent
            async for message in client.iter_messages(CHAT_ID, limit=100, offset_date=None):
                if message.date.replace(tzinfo=None) < new_from_date.replace(tzinfo=None):
                    break

                if message.text is not None:
                    # Process message
                    data = process_message(message.text)

                    # Add message metadata
                    data["Message_ID"] = str(message.id)
                    data["Message_Date"] = message.date.strftime("%Y-%m-%d")
                    data["Message_Time"] = message.date.strftime("%H:%M:%S")

                    # Add data to columns
                    for col in column_names:
                        if col in data:
                            all_data[col].append(data[col])
                        else:
                            all_data[col].append("")

                    msg_count += 1

            # Create DataFrame with extended range
            df = pd.DataFrame(all_data)

            # Sort by date (newest first)
            if not df.empty and 'Message_Date' in df.columns:
                df['Message_Date'] = pd.to_datetime(df['Message_Date'])
                df = df.sort_values('Message_Date', ascending=False)

                # Convert dates back to string
                df['Message_Date'] = df['Message_Date'].dt.strftime('%Y-%m-%d')

                # Get only the most recent N messages where N = days_ago
                if len(df) > days_ago:
                    df = df.head(days_ago)

            # Disconnect
            await client.disconnect()

            status_placeholder.success(f"Fetched {len(df)} most recent messages")

        return df, msg_count

    except Exception as e:
        status_placeholder.error(f"Error connecting to Telegram: {str(e)}")
        with debug_expander:
            st.exception(e)  # Show the full exception for debugging
        try:
            await client.disconnect()
        except:
            pass
        return None, 0


# ============================================
# SIDEBAR FILTERS
# ============================================

st.sidebar.header("Filter Options")

exchange_options = {
    "Hong Kong": "HKEX",
    "US": "BATS",
    "Shanghai": "SSE_DLY",
    "Shenzhen": "ZSE_DLY",
    "Forex": "OANDA"
}

selected_exchange = st.sidebar.selectbox(
    "Select Exchange",
    list(exchange_options.keys())
)
exchange_filter = exchange_options[selected_exchange]

# Date range selection method
date_range_method = st.sidebar.radio(
    "Date Range Selection Method",
    ["Days to Look Back", "Custom Date Range"]
)

if date_range_method == "Days to Look Back":
    # Original method - use days to look back
    days_ago = st.sidebar.number_input(
        "Number of days to look back",
        min_value=1,
        max_value=20,
        value=1
    )
    to_date = datetime.now()  # Current date and time
    from_date = to_date - timedelta(days=days_ago)
    st.sidebar.info(f"Fetching data from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")

    # Set custom date variables to None
    custom_from_date = None
    custom_to_date = None
else:
    # Custom date range method
    col1, col2 = st.sidebar.columns(2)
    with col1:
        custom_from_date = st.date_input(
            "From Date",
            value=datetime.now().date() - timedelta(days=7),
            max_value=datetime.now().date()
        )
    with col2:
        custom_to_date = st.date_input(
            "To Date",
            value=datetime.now().date(),
            max_value=datetime.now().date(),
            min_value=custom_from_date
        )

    # Convert dates to datetime objects with time components for proper filtering
    from_date = datetime.combine(custom_from_date, datetime.min.time())  # Start of day (00:00:00)
    to_date = datetime.combine(custom_to_date, datetime.max.time())  # End of day (23:59:59)

    # Calculate days_ago for fallback functionality
    days_ago = (custom_to_date - custom_from_date).days + 1

    st.sidebar.info(f"Fetching data from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')} ({days_ago} days)")

# Add sorting options
st.sidebar.header("Sorting Options")

sort_by_sentiment = st.sidebar.checkbox(
    "Sort by 看好看淡 (看好 first)",
    value=True  # Default checked
)

sort_by_pl = st.sidebar.checkbox(
    "Sort by % P/L",
    value=False
)

# Sort order for P/L (only shown if sort_by_pl is checked)
pl_sort_order = None
if sort_by_pl:
    pl_sort_order = st.sidebar.radio(
        "P/L Sort Order",
        ["Highest First", "Lowest First"],
        index=0  # Default to Highest First
    )

# Add refresh button
refresh = st.sidebar.button("Refresh Data")


# ============================================
# SORTING FUNCTION
# ============================================

def apply_sorting(df):
    """Function to apply sorting to dataframe"""
    if df is None or df.empty:
        return df

    # Create a copy to avoid modifying the original
    sorted_df = df.copy()

    # Convert % P/L to numeric for sorting
    sorted_df['% P/L_numeric'] = pd.to_numeric(sorted_df['% P/L'], errors='coerce')

    # Apply sorting based on selection
    if sort_by_sentiment and sort_by_pl:
        # First sort by P/L
        if pl_sort_order == "Highest First":
            sorted_df = sorted_df.sort_values('% P/L_numeric', ascending=False, na_position='last')
        else:
            sorted_df = sorted_df.sort_values('% P/L_numeric', ascending=True, na_position='last')

        # Then sort by sentiment (好 first)
        sorted_df = sorted_df.sort_values(['看好看淡', '% P/L_numeric'],
                                          ascending=[True, False if pl_sort_order == "Highest First" else True],
                                          na_position='last')
    elif sort_by_sentiment:
        # Sort by sentiment only (好 first)
        sorted_df = sorted_df.sort_values('看好看淡', ascending=True, na_position='last')
    elif sort_by_pl:
        # Sort by P/L only
        if pl_sort_order == "Highest First":
            sorted_df = sorted_df.sort_values('% P/L_numeric', ascending=False, na_position='last')
        else:
            sorted_df = sorted_df.sort_values('% P/L_numeric', ascending=True, na_position='last')

    # Drop the numeric column used for sorting
    sorted_df = sorted_df.drop('% P/L_numeric', axis=1)

    return sorted_df


# ============================================
# MAIN APP - TABS
# ============================================

tab1, tab2 = st.tabs(["Fetch from Telegram", "Upload CSV"])

# Tab 1: Fetch from Telegram
with tab1:
    st.write("""
    ## Fetch from Telegram
    Click the button below to fetch data directly from Telegram.
    """)

    # FIX: Separate the button declaration from the conditional check
    fetch_button = st.button("Fetch Signals from Telegram")

    if fetch_button or refresh:
        # Run the async function in the event loop with the selected date range
        if date_range_method == "Days to Look Back":
            df, msg_count = asyncio.run(fetch_telegram_data(days_ago))
        else:
            df, msg_count = asyncio.run(fetch_telegram_data(days_ago, from_date, to_date))

        if df is not None and len(df) > 0:
            # Process data to get the required format
            result_df = process_signal_data(df, exchange_filter)

            if len(result_df) > 0:
                # Apply sorting
                sorted_result_df = apply_sorting(result_df)

                # Count different signal types
                buy_signals = len(sorted_result_df[sorted_result_df['看好看淡'] == '好'])
                sell_signals = len(sorted_result_df[sorted_result_df['看好看淡'] == '淡'])
                valid_buy_signals = len(sorted_result_df[(sorted_result_df['看好看淡'] == '好') & (sorted_result_df['Valid Signal?'] == 'Yes')])
                valid_sell_signals = len(sorted_result_df[(sorted_result_df['看好看淡'] == '淡') & (sorted_result_df['Valid Signal?'] == 'Yes')])

                # Find the closest date to today in the data
                today = datetime.now().date()
                closest_date = None
                min_days_diff = float('inf')

                if '日期' in sorted_result_df.columns and not sorted_result_df.empty:
                    for date_str in sorted_result_df['日期'].dropna().unique():
                        try:
                            date_obj = pd.to_datetime(date_str).date()
                            days_diff = abs((date_obj - today).days)
                            if days_diff < min_days_diff:
                                min_days_diff = days_diff
                                closest_date = date_obj
                        except:
                            pass

                # Display signal statistics in a visible box
                st.success(f"找到 {len(sorted_result_df)} 個信號")

                # Create a visually distinct box for statistics
                st.markdown("""
                <style>
                .stat-box {
                    background-color: #e6f3ff;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #99ccff;
                }
                </style>
                <div class="stat-box">
                <h3 style="color:#0066cc;">信號統計摘要</h3>
                """, unsafe_allow_html=True)

                if closest_date:
                    st.markdown(f"<b>最近日期:</b> {closest_date.strftime('%Y-%m-%d')} (與今天相差 {min_days_diff} 天)<br>", unsafe_allow_html=True)

                # Show statistics in HTML for better visibility
                st.markdown(f"""
                <table style="width:100%;">
                <tr>
                <td style="width:33%; vertical-align:top;">
                <div><b>買入信號數量 (好):</b> {buy_signals}</div>
                <div><b>賣出信號數量 (淡):</b> {sell_signals}</div>
                <div><b>初始動量比率:</b> {buy_signals} 好 : {sell_signals} 淡</div>
                </td>
                <td style="width:33%; vertical-align:top;">
                <div><b>有效買入信號:</b> {valid_buy_signals}</div>
                <div><b>有效賣出信號:</b> {valid_sell_signals}</div>
                <div><b>實際動量比率:</b> {valid_buy_signals} 好 : {valid_sell_signals} 淡</div>
                </td>
                <td style="width:33%; vertical-align:top;">
                """, unsafe_allow_html=True)

                # Calculate percentages
                bullish_pct = round((valid_buy_signals / buy_signals) * 100, 1) if buy_signals > 0 else 0
                bearish_pct = round((valid_sell_signals / sell_signals) * 100, 1) if sell_signals > 0 else 0

                st.markdown(f"""
                <div><b>看好動量強度:</b> {buy_signals} 好 : {valid_buy_signals} 有效好 ({bullish_pct}%)</div>
                <div><b>看淡動量強度:</b> {sell_signals} 淡 : {valid_sell_signals} 有效淡 ({bearish_pct}%)</div>
                </td>
                </tr>
                </table>
                </div>
                """, unsafe_allow_html=True)

                # Display the dataframe
                st.subheader("信號詳細數據")
                st.dataframe(sorted_result_df, use_container_width=True)

                # Add download buttons
                csv = sorted_result_df.to_csv(index=False)
                st.download_button(
                    label=f"下載 {exchange_filter} 信號",
                    data=csv,
                    file_name=f"{exchange_filter}_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

                raw_csv = df.to_csv(index=False)
                st.download_button(
                    label="下載所有原始數據 (用於將來上傳)",
                    data=raw_csv,
                    file_name=f"telegram_raw_data_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="raw_download"
                )

                # Save signal statistics to day-by-day history
                # Use the closest date found in the signals as the date for these statistics
                date_str = closest_date.strftime('%Y-%m-%d') if closest_date else datetime.now().strftime('%Y-%m-%d')

                # Save day-specific stats (not accumulated)
                save_signal_stats(
                    date_str=date_str,
                    buy_signals=buy_signals,
                    valid_buy_signals=valid_buy_signals,
                    sell_signals=sell_signals,
                    valid_sell_signals=valid_sell_signals,
                    exchange=exchange_filter
                )

                # Display day-by-day signal history table
                st.markdown("---")
                display_signal_history_table(exchange_filter)
            else:
                st.warning(f"未找到 {exchange_filter} 的信號")
        else:
            st.warning("沒有找到指定日期範圍內的訊息")

# Tab 2: Upload CSV
with tab2:
    st.write("""
    ## Upload CSV
    If you have a CSV export of Telegram data, upload it here.
    """)

    # File uploader
    uploaded_file = st.file_uploader("Upload Telegram data CSV", type=["csv"])

    if uploaded_file is not None:
        # Load data from file
        try:
            data = pd.read_csv(uploaded_file)

            # Filter by date if date column exists
            if 'Message_Date' in data.columns:
                try:
                    data['Message_Date'] = pd.to_datetime(data['Message_Date'])

                    # Apply date filtering based on the selected method
                    filtered_data = data[(data['Message_Date'].dt.date >= from_date.date()) &
                                         (data['Message_Date'].dt.date <= to_date.date())]

                    # Convert back to string for display
                    filtered_data['Message_Date'] = filtered_data['Message_Date'].dt.strftime('%Y-%m-%d')
                except:
                    # If date conversion fails, use the original data
                    filtered_data = data
                    st.warning("Could not filter by date - date format not recognized")
            else:
                filtered_data = data
                st.warning("No 'Message_Date' column found in data - cannot filter by date")

            # Process data to get the required format
            result_df = process_signal_data(filtered_data, exchange_filter)

            if len(result_df) > 0:
                # Apply sorting
                sorted_result_df = apply_sorting(result_df)

                # Count different signal types
                buy_signals = len(sorted_result_df[sorted_result_df['看好看淡'] == '好'])
                sell_signals = len(sorted_result_df[sorted_result_df['看好看淡'] == '淡'])
                valid_buy_signals = len(sorted_result_df[(sorted_result_df['看好看淡'] == '好') & (sorted_result_df['Valid Signal?'] == 'Yes')])
                valid_sell_signals = len(sorted_result_df[(sorted_result_df['看好看淡'] == '淡') & (sorted_result_df['Valid Signal?'] == 'Yes')])

                # Find the closest date to today in the data
                today = datetime.now().date()
                closest_date = None
                min_days_diff = float('inf')

                if '日期' in sorted_result_df.columns and not sorted_result_df.empty:
                    for date_str in sorted_result_df['日期'].dropna().unique():
                        try:
                            date_obj = pd.to_datetime(date_str).date()
                            days_diff = abs((date_obj - today).days)
                            if days_diff < min_days_diff:
                                min_days_diff = days_diff
                                closest_date = date_obj
                        except:
                            pass

                # Display signal statistics in a visible box
                st.success(f"找到 {len(sorted_result_df)} 個信號")

                # Create a visually distinct box for statistics
                st.markdown("""
                <style>
                .stat-box {
                    background-color: #e6f3ff;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #99ccff;
                }
                </style>
                <div class="stat-box">
                <h3 style="color:#0066cc;">信號統計摘要</h3>
                """, unsafe_allow_html=True)

                if closest_date:
                    st.markdown(f"<b>最近日期:</b> {closest_date.strftime('%Y-%m-%d')} (與今天相差 {min_days_diff} 天)<br>", unsafe_allow_html=True)

                # Show statistics in HTML for better visibility - IMPORTANT: This is the fixed part
                st.markdown(f"""
                <table style="width:100%;">
                <tr>
                <td style="width:33%; vertical-align:top;">
                <div><b>買入信號數量 (好):</b> {buy_signals}</div>
                <div><b>賣出信號數量 (淡):</b> {sell_signals}</div>
                <div><b>初始動量比率:</b> {buy_signals} 好 : {sell_signals} 淡</div>
                </td>
                <td style="width:33%; vertical-align:top;">
                <div><b>有效買入信號:</b> {valid_buy_signals}</div>
                <div><b>有效賣出信號:</b> {valid_sell_signals}</div>
                <div><b>實際動量比率:</b> {valid_buy_signals} 好 : {valid_sell_signals} 淡</div>
                </td>
                <td style="width:33%; vertical-align:top;">
                """, unsafe_allow_html=True)

                # Calculate percentages
                bullish_pct = round((valid_buy_signals / buy_signals) * 100, 1) if buy_signals > 0 else 0
                bearish_pct = round((valid_sell_signals / sell_signals) * 100, 1) if sell_signals > 0 else 0

                st.markdown(f"""
                <div><b>看好動量強度:</b> {buy_signals} 好 : {valid_buy_signals} 有效好 ({bullish_pct}%)</div>
                <div><b>看淡動量強度:</b> {sell_signals} 淡 : {valid_sell_signals} 有效淡 ({bearish_pct}%)</div>
                </td>
                </tr>
                </table>
                </div>
                """, unsafe_allow_html=True)

                st.subheader("信號詳細數據")
                st.dataframe(sorted_result_df, use_container_width=True)

                # Add download button
                csv = sorted_result_df.to_csv(index=False)
                st.download_button(
                    label=f"下載 {exchange_filter} 信號",
                    data=csv,
                    file_name=f"{exchange_filter}_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"未找到 {exchange_filter} 的信號")

        except Exception as e:
            st.error(f"處理檔案時出錯: {str(e)}")
            st.exception(e)  # Show the full exception for debugging


# ============================================
# HISTORY BUILDING FUNCTION
# ============================================

def add_history_for_multiple_dates():
    """
    Function to fetch data for multiple dates and add to history
    This will help build up the day-by-day history table
    """
    dates_to_check = [
        (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        for i in range(14)  # Check last 14 days
    ]

    st.info("Building signal history for multiple dates...")
    progress_bar = st.progress(0)

    for i, date_str in enumerate(dates_to_check):
        # Update progress
        progress_bar.progress((i + 1) / len(dates_to_check))

        # Parse to datetime objects
        from_date = datetime.strptime(date_str, '%Y-%m-%d')
        to_date = from_date + timedelta(days=1) - timedelta(seconds=1)  # End of the day

        # Fetch data for just this single day
        try:
            df, _ = asyncio.run(fetch_telegram_data(1, from_date, to_date))

            if df is not None and len(df) > 0:
                # Process data
                result_df = process_signal_data(df, exchange_filter)

                if len(result_df) > 0:
                    # Count signals for this specific day
                    buy_signals = len(result_df[result_df['看好看淡'] == '好'])
                    sell_signals = len(result_df[result_df['看好看淡'] == '淡'])
                    valid_buy_signals = len(result_df[(result_df['看好看淡'] == '好') & (result_df['Valid Signal?'] == 'Yes')])
                    valid_sell_signals = len(result_df[(result_df['看好看淡'] == '淡') & (result_df['Valid Signal?'] == 'Yes')])

                    # Save this day's statistics
                    save_signal_stats(
                        date_str=date_str,
                        buy_signals=buy_signals,
                        valid_buy_signals=valid_buy_signals,
                        sell_signals=sell_signals,
                        valid_sell_signals=valid_sell_signals,
                        exchange=exchange_filter
                    )

        except Exception as e:
            st.error(f"Error processing date {date_str}: {str(e)}")

    st.success("History building complete!")


# Add a button to build history in your sidebar
st.sidebar.markdown("---")
if st.sidebar.button("Build Signal History (All Dates)"):
    add_history_for_multiple_dates()

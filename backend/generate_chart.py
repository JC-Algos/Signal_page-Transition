#!/usr/bin/env python3
"""
Generate candlestick chart with EMAs and Volume Profile
Uses mplfinance for professional-looking charts
"""

import os
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pytz

# Check if mplfinance is available
try:
    import mplfinance as mpf
except ImportError:
    print("Installing mplfinance...")
    import subprocess
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'mplfinance', '-q'])
    import mplfinance as mpf


def detect_chart_patterns(data: pd.DataFrame) -> dict:
    """
    Detect chart patterns: Engulfing, Double Top/Bottom, Head & Shoulders
    
    Returns dict with pattern locations and details
    """
    patterns = {
        'bullish_engulfing': [],
        'bearish_engulfing': [],
        'double_top': [],
        'double_bottom': [],
        'head_shoulders': [],
        'inv_head_shoulders': []
    }
    
    # Need at least 30 days of data
    if len(data) < 30:
        return patterns
    
    # --- Engulfing Patterns ---
    gap_tolerance = 0.01  # 1% tolerance
    for i in range(1, len(data)):
        curr = data.iloc[i]
        prev = data.iloc[i-1]
        
        curr_body = abs(curr['Close'] - curr['Open'])
        prev_body = abs(prev['Close'] - prev['Open'])
        
        if prev_body == 0:
            continue
            
        # Bullish Engulfing
        if (prev['Close'] < prev['Open'] and  # prev red
            curr['Close'] > curr['Open'] and  # curr green
            curr['Open'] <= prev['Close'] * (1 + gap_tolerance) and
            curr['Close'] >= prev['Open'] and
            curr_body > prev_body * 1.3):
            patterns['bullish_engulfing'].append({
                'idx': i,
                'date': data.index[i],
                'price': curr['Low']
            })
        
        # Bearish Engulfing
        if (prev['Close'] > prev['Open'] and  # prev green
            curr['Close'] < curr['Open'] and  # curr red
            curr['Open'] >= prev['Close'] * (1 - gap_tolerance) and
            curr['Close'] <= prev['Open'] and
            curr_body > prev_body * 1.3):
            patterns['bearish_engulfing'].append({
                'idx': i,
                'date': data.index[i],
                'price': curr['High']
            })
    
    # --- Double Top/Bottom Detection (min 10 days apart, max 60 days) ---
    # Find local peaks and troughs
    window = 5  # days to look around for local extrema
    
    peaks = []
    troughs = []
    
    for i in range(window, len(data) - window):
        # Local high
        if data['High'].iloc[i] == data['High'].iloc[i-window:i+window+1].max():
            peaks.append({'idx': i, 'price': data['High'].iloc[i], 'date': data.index[i]})
        # Local low
        if data['Low'].iloc[i] == data['Low'].iloc[i-window:i+window+1].min():
            troughs.append({'idx': i, 'price': data['Low'].iloc[i], 'date': data.index[i]})
    
    # Find Double Tops (two peaks at similar levels, at least 10 days apart to filter noise)
    price_tolerance = 0.03  # 3% price tolerance (max distance between tops)
    for i, p1 in enumerate(peaks):
        for p2 in peaks[i+1:]:
            days_apart = p2['idx'] - p1['idx']
            if 10 <= days_apart <= 60:  # Min 10 days to filter noise, max 60 days
                price_diff = abs(p1['price'] - p2['price']) / p1['price']
                if price_diff < price_tolerance:
                    # Check for valley between peaks (neckline)
                    valley_data = data.iloc[p1['idx']:p2['idx']+1]
                    valley_low = valley_data['Low'].min()
                    avg_peak = (p1['price'] + p2['price']) / 2
                    if valley_low < avg_peak * 0.95:  # Valley at least 5% below peaks
                        patterns['double_top'].append({
                            'peak1': p1,
                            'peak2': p2,
                            'neckline': valley_low
                        })
    
    # Find Double Bottoms (same parameters as double tops)
    for i, t1 in enumerate(troughs):
        for t2 in troughs[i+1:]:
            days_apart = t2['idx'] - t1['idx']
            if 10 <= days_apart <= 60:  # Min 10 days to filter noise
                price_diff = abs(t1['price'] - t2['price']) / t1['price']
                if price_diff < price_tolerance:
                    # Check for peak between troughs
                    peak_data = data.iloc[t1['idx']:t2['idx']+1]
                    peak_high = peak_data['High'].max()
                    avg_trough = (t1['price'] + t2['price']) / 2
                    if peak_high > avg_trough * 1.05:
                        patterns['double_bottom'].append({
                            'trough1': t1,
                            'trough2': t2,
                            'neckline': peak_high
                        })
    
    # --- Head and Shoulders Detection ---
    # Need 3 peaks: left shoulder, head (highest), right shoulder
    for i in range(len(peaks) - 2):
        left = peaks[i]
        head = peaks[i + 1]
        right = peaks[i + 2]
        
        # Head must be higher than shoulders
        if head['price'] > left['price'] and head['price'] > right['price']:
            # Shoulders should be at similar levels (within 5%)
            shoulder_diff = abs(left['price'] - right['price']) / left['price']
            if shoulder_diff < 0.05:
                # Check timeframe (head within 60 days of shoulders)
                if (head['idx'] - left['idx'] <= 30 and 
                    right['idx'] - head['idx'] <= 30):
                    # Find neckline (connect troughs between shoulders and head)
                    left_trough = data['Low'].iloc[left['idx']:head['idx']].min()
                    right_trough = data['Low'].iloc[head['idx']:right['idx']+1].min()
                    neckline = (left_trough + right_trough) / 2
                    
                    patterns['head_shoulders'].append({
                        'left_shoulder': left,
                        'head': head,
                        'right_shoulder': right,
                        'neckline': neckline
                    })
    
    # --- Inverse Head and Shoulders ---
    for i in range(len(troughs) - 2):
        left = troughs[i]
        head = troughs[i + 1]
        right = troughs[i + 2]
        
        # Head must be lower than shoulders
        if head['price'] < left['price'] and head['price'] < right['price']:
            shoulder_diff = abs(left['price'] - right['price']) / left['price']
            if shoulder_diff < 0.05:
                if (head['idx'] - left['idx'] <= 30 and 
                    right['idx'] - head['idx'] <= 30):
                    left_peak = data['High'].iloc[left['idx']:head['idx']].max()
                    right_peak = data['High'].iloc[head['idx']:right['idx']+1].max()
                    neckline = (left_peak + right_peak) / 2
                    
                    patterns['inv_head_shoulders'].append({
                        'left_shoulder': left,
                        'head': head,
                        'right_shoulder': right,
                        'neckline': neckline
                    })
    
    return patterns


def calculate_volume_profile(data: pd.DataFrame, num_bins: int = 30) -> tuple:
    """
    Calculate Volume Profile data
    
    Returns:
        price_levels: array of price levels
        volumes: volume at each price level
        poc: Point of Control (highest volume price)
        vah: Value Area High
        val: Value Area Low
    """
    price_min = data['Low'].min()
    price_max = data['High'].max()
    bin_size = (price_max - price_min) / num_bins
    
    # Initialize volume profile
    price_levels = []
    volumes = []
    
    for i in range(num_bins):
        bin_low = price_min + (i * bin_size)
        bin_high = bin_low + bin_size
        bin_mid = (bin_low + bin_high) / 2
        price_levels.append(bin_mid)
        
        # Calculate volume in this price range
        vol = 0
        for idx, row in data.iterrows():
            if row['High'] >= bin_low and row['Low'] <= bin_high:
                # Proportional volume distribution
                candle_range = row['High'] - row['Low'] if row['High'] > row['Low'] else 1
                overlap_low = max(row['Low'], bin_low)
                overlap_high = min(row['High'], bin_high)
                overlap_pct = (overlap_high - overlap_low) / candle_range
                vol += row['Volume'] * overlap_pct
        volumes.append(vol)
    
    # Find POC (Point of Control)
    max_vol_idx = np.argmax(volumes)
    poc = price_levels[max_vol_idx]
    
    # Calculate Value Area (70% of volume)
    total_vol = sum(volumes)
    target_vol = total_vol * 0.70
    
    # Start from POC and expand outward
    accumulated = volumes[max_vol_idx]
    lower_idx = max_vol_idx
    upper_idx = max_vol_idx
    
    while accumulated < target_vol:
        # Expand to the side with more volume
        lower_vol = volumes[lower_idx - 1] if lower_idx > 0 else 0
        upper_vol = volumes[upper_idx + 1] if upper_idx < len(volumes) - 1 else 0
        
        if lower_vol >= upper_vol and lower_idx > 0:
            lower_idx -= 1
            accumulated += lower_vol
        elif upper_idx < len(volumes) - 1:
            upper_idx += 1
            accumulated += upper_vol
        else:
            break
    
    val = price_levels[lower_idx]
    vah = price_levels[upper_idx]
    
    return np.array(price_levels), np.array(volumes), poc, vah, val


def generate_chart(symbol: str, market: str = 'HK', period: str = '13mo', 
                   output_dir: str = '/root/clawd/research/charts') -> str:
    """
    Generate a professional candlestick chart with EMAs
    
    Args:
        symbol: Stock symbol (e.g., "0700", "AAPL")
        market: Market (HK, US)
        period: Data period (1y, 2y, etc.)
        output_dir: Directory to save the chart
        
    Returns:
        Path to the generated chart image
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Format symbol for Yahoo Finance
    if market.upper() == 'HK':
        # Remove .HK if already present to avoid duplication
        clean_symbol = symbol.replace('.HK', '')
        yf_symbol = f"{clean_symbol.zfill(4)}.HK"
    else:
        yf_symbol = symbol
    
    print(f"📊 Generating chart for {yf_symbol}...")
    
    # Fetch 2 years of data for EMA200 calculation, but display only 6 months
    try:
        # Always fetch 2 years for accurate EMA200
        # Use market timezone to get correct date
        if market.upper() == 'HK':
            hk_tz = pytz.timezone('Asia/Hong_Kong')
            end_date = datetime.now(hk_tz).replace(tzinfo=None)  # Convert to naive datetime for yfinance
        else:
            end_date = datetime.now()
        
        start_date = end_date - timedelta(days=730)  # 2 years
        full_data = yf.download(yf_symbol, start=start_date, end=end_date, interval='1d', progress=False)
        if full_data.empty:
            print(f"❌ No data found for {yf_symbol}")
            return None
        
        # Flatten multi-index columns if present
        if isinstance(full_data.columns, pd.MultiIndex):
            full_data.columns = full_data.columns.get_level_values(0)
        
        # Ensure proper column names for mplfinance
        full_data = full_data.rename(columns={
            'Open': 'Open', 'High': 'High', 'Low': 'Low', 
            'Close': 'Close', 'Volume': 'Volume'
        })
        
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return None
    
    # Calculate EMAs on full 2-year data (for accurate EMA200)
    full_data['EMA10'] = full_data['Close'].ewm(span=10, adjust=False).mean()
    full_data['EMA20'] = full_data['Close'].ewm(span=20, adjust=False).mean()
    full_data['EMA60'] = full_data['Close'].ewm(span=60, adjust=False).mean()
    full_data['EMA200'] = full_data['Close'].ewm(span=200, adjust=False).mean()
    
    # Use only last 6 months (126 trading days) for display
    display_days = 126  # ~6 months of trading days
    data = full_data.tail(display_days).copy()
    print(f"📊 Displaying {len(data)} days (6 months), EMAs calculated from {len(full_data)} days (2 years)")
    
    # Create additional plots for EMAs - all blue tones, increasing thickness
    ema_plots = [
        mpf.make_addplot(data['EMA10'], color='#87CEEB', width=1, label='EMA10'),    # Light sky blue, thinnest
        mpf.make_addplot(data['EMA20'], color='#4169E1', width=1.5, label='EMA20'),  # Royal blue
        mpf.make_addplot(data['EMA60'], color='#0066CC', width=2.5, label='EMA60'),  # Medium blue
        mpf.make_addplot(data['EMA200'], color='#00008B', width=5, label='EMA200'),  # Deep navy blue, thickest
    ]
    
    # Get stock info for title
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        name = info.get('shortName', info.get('longName', yf_symbol))
    except:
        name = yf_symbol
    
    # Current price info
    current_price = data['Close'].iloc[-1]
    prev_close = data['Close'].iloc[-2] if len(data) > 1 else current_price
    change = current_price - prev_close
    change_pct = (change / prev_close) * 100
    
    # Chart title
    title = f"{name} ({yf_symbol}) - 6M Daily + YTD Volume Profile\n"
    title += f"Price: {current_price:.2f} ({change:+.2f}, {change_pct:+.2f}%)"
    
    # Style configuration
    mc = mpf.make_marketcolors(
        up='#26A69A', down='#EF5350',
        edge='inherit',
        wick={'up': '#26A69A', 'down': '#EF5350'},
        volume={'up': '#26A69A', 'down': '#EF5350'}
    )
    
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle='-',
        gridcolor='#E0E0E0',
        facecolor='white',
        edgecolor='#CCCCCC',
        figcolor='white',
        y_on_right=True
    )
    
    # Output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_dir}/{symbol}_{market}_{period}_{timestamp}.png"
    
    # Calculate YTD Volume Profile (from Jan 1 of current year)
    current_year = datetime.now().year
    ytd_start = f"{current_year}-01-01"
    ytd_data = data[data.index >= ytd_start]
    
    if len(ytd_data) < 10:
        # Fallback to last 6 months if YTD is too short
        ytd_data = data.tail(126)  # ~6 months of trading days
    
    print(f"📊 Calculating YTD Volume Profile ({len(ytd_data)} days from {ytd_data.index[0].strftime('%Y-%m-%d')})")
    
    price_levels, volumes, poc, vah, val = calculate_volume_profile(ytd_data)
    
    # Generate chart
    fig, axes = mpf.plot(
        data,
        type='candle',
        style=style,
        title=title,
        ylabel='Price',
        ylabel_lower='Volume',
        volume=True,
        addplot=ema_plots,
        figsize=(14, 10),
        returnfig=True,
        panel_ratios=(4, 1)
    )
    
    # Get the price axis
    ax_price = axes[0]
    
    # Draw only VAL, VAH, PoC as horizontal lines (no mountain profile)
    # PoC - Point of Control (most traded price)
    ax_price.axhline(y=poc, color='#FF6600', linestyle='-', linewidth=2, alpha=0.9, zorder=5)
    # VAH - Value Area High
    ax_price.axhline(y=vah, color='#0066FF', linestyle='--', linewidth=1.5, alpha=0.8, zorder=5)
    # VAL - Value Area Low  
    ax_price.axhline(y=val, color='#0066FF', linestyle='--', linewidth=1.5, alpha=0.8, zorder=5)
    
    # Add prominent labels on the right side
    ax_price.text(len(data) * 1.02, poc, f'PoC {poc:.2f}', fontsize=10, 
                  color='#FF6600', fontweight='bold', va='center',
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#FF6600', alpha=0.9))
    ax_price.text(len(data) * 1.02, vah, f'VAH {vah:.2f}', fontsize=9, 
                  color='#0066FF', fontweight='bold', va='center',
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#0066FF', alpha=0.9))
    ax_price.text(len(data) * 1.02, val, f'VAL {val:.2f}', fontsize=9, 
                  color='#0066FF', fontweight='bold', va='center',
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#0066FF', alpha=0.9))
    
    # Add EMA legend with correct colors and line widths
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#87CEEB', linewidth=1, label='EMA10'),
        Line2D([0], [0], color='#4169E1', linewidth=1.5, label='EMA20'),
        Line2D([0], [0], color='#0066CC', linewidth=2.5, label='EMA60'),
        Line2D([0], [0], color='#00008B', linewidth=5, label='EMA200'),
    ]
    ax_price.legend(handles=legend_elements, loc='upper left', fontsize=8)
    
    # --- Detect and Draw Chart Patterns ---
    print("🔍 Detecting chart patterns...")
    patterns = detect_chart_patterns(data)
    
    # Draw Bullish Engulfing (green arrow up)
    for p in patterns['bullish_engulfing'][-5:]:  # Last 5 only
        idx = p['idx']
        ax_price.annotate('▲', xy=(idx, p['price']), 
                         fontsize=12, color='#00AA00', fontweight='bold',
                         ha='center', va='top')
    
    # Draw Bearish Engulfing (red arrow down)
    for p in patterns['bearish_engulfing'][-5:]:
        idx = p['idx']
        ax_price.annotate('▼', xy=(idx, p['price']),
                         fontsize=12, color='#DD0000', fontweight='bold',
                         ha='center', va='bottom')
    
    # Draw Double Tops
    for dt in patterns['double_top'][-2:]:  # Last 2 only
        p1, p2 = dt['peak1'], dt['peak2']
        # Draw line connecting peaks
        ax_price.plot([p1['idx'], p2['idx']], [p1['price'], p2['price']], 
                     color='#FF4444', linestyle='-', linewidth=2, alpha=0.8)
        # Draw neckline
        ax_price.axhline(y=dt['neckline'], xmin=p1['idx']/len(data), xmax=p2['idx']/len(data),
                        color='#FF4444', linestyle='--', linewidth=1, alpha=0.6)
        # Label
        mid_idx = (p1['idx'] + p2['idx']) / 2
        ax_price.annotate('Double Top', xy=(mid_idx, p1['price']),
                         fontsize=8, color='#FF4444', fontweight='bold',
                         ha='center', va='bottom')
    
    # Draw Double Bottoms
    for db in patterns['double_bottom'][-2:]:
        t1, t2 = db['trough1'], db['trough2']
        ax_price.plot([t1['idx'], t2['idx']], [t1['price'], t2['price']], 
                     color='#44AA44', linestyle='-', linewidth=2, alpha=0.8)
        ax_price.axhline(y=db['neckline'], xmin=t1['idx']/len(data), xmax=t2['idx']/len(data),
                        color='#44AA44', linestyle='--', linewidth=1, alpha=0.6)
        mid_idx = (t1['idx'] + t2['idx']) / 2
        ax_price.annotate('Double Bottom', xy=(mid_idx, t1['price']),
                         fontsize=8, color='#44AA44', fontweight='bold',
                         ha='center', va='top')
    
    # Draw Head and Shoulders
    for hs in patterns['head_shoulders'][-1:]:  # Last 1 only
        ls, h, rs = hs['left_shoulder'], hs['head'], hs['right_shoulder']
        # Draw pattern outline
        ax_price.plot([ls['idx'], h['idx'], rs['idx']], 
                     [ls['price'], h['price'], rs['price']], 
                     color='#FF6600', linestyle='-', linewidth=2, marker='o', markersize=6, alpha=0.8)
        # Draw neckline
        ax_price.axhline(y=hs['neckline'], color='#FF6600', linestyle='--', linewidth=1.5, alpha=0.7)
        ax_price.annotate('H&S', xy=(h['idx'], h['price']),
                         fontsize=9, color='#FF6600', fontweight='bold',
                         ha='center', va='bottom')
    
    # Draw Inverse Head and Shoulders
    for ihs in patterns['inv_head_shoulders'][-1:]:
        ls, h, rs = ihs['left_shoulder'], ihs['head'], ihs['right_shoulder']
        ax_price.plot([ls['idx'], h['idx'], rs['idx']], 
                     [ls['price'], h['price'], rs['price']], 
                     color='#00AA66', linestyle='-', linewidth=2, marker='o', markersize=6, alpha=0.8)
        ax_price.axhline(y=ihs['neckline'], color='#00AA66', linestyle='--', linewidth=1.5, alpha=0.7)
        ax_price.annotate('Inv H&S', xy=(h['idx'], h['price']),
                         fontsize=9, color='#00AA66', fontweight='bold',
                         ha='center', va='top')
    
    # Print pattern summary
    pattern_count = sum(len(v) for v in patterns.values())
    print(f"📊 Found {pattern_count} patterns: " + 
          f"Engulf↑{len(patterns['bullish_engulfing'])} Engulf↓{len(patterns['bearish_engulfing'])} " +
          f"DblTop{len(patterns['double_top'])} DblBot{len(patterns['double_bottom'])} " +
          f"H&S{len(patterns['head_shoulders'])} InvH&S{len(patterns['inv_head_shoulders'])}")
    
    # Adjust x-axis (no extra space needed without VP mountain)
    ax_price.set_xlim(-5, len(data) * 1.08)
    
    # Save chart
    fig.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
    
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"✅ Chart saved: {output_file} ({file_size:,} bytes)")
        return output_file
    
    return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Stock Chart')
    parser.add_argument('symbol', help='Stock symbol (e.g., 0700, AAPL)')
    parser.add_argument('--market', '-m', default='HK', help='Market: HK or US')
    parser.add_argument('--period', '-p', default='13mo', help='Period: 13mo (default), 1y, 2y')
    
    args = parser.parse_args()
    
    chart_path = generate_chart(args.symbol, args.market, args.period)
    if chart_path:
        print(f"\n📈 Chart: {chart_path}")
